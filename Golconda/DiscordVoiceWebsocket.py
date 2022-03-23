"""
The MIT License (MIT)
Copyright (c) 2015-present Rapptz
Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
import asyncio
import concurrent
import json
import logging
import struct
import sys
import threading
import traceback

from collections import deque
import time
from typing import TypeVar, TYPE_CHECKING, Optional, Callable, Coroutine, Any

import aiohttp

DVWS = TypeVar("DVWS", bound="DiscordVoiceWebSocket")
log = logging.Logger("Websocket")


class ConnectionClosed(Exception):
    """Exception that's raised when the gateway connection is
    closed for reasons that could not be handled internally.
    Attributes
    -----------
    code: :class:`int`
        The close code of the websocket.
    reason: :class:`str`
        The reason provided for the closure.
    shard_id: Optional[:class:`int`]
        The shard ID that got closed if applicable.
    """

    def __init__(self, socket, *, shard_id: Optional[int], code: Optional[int] = None):
        # This exception is just the same exception except
        # reconfigured to subclass ClientException for users
        self.code: int = code or socket.close_code or -1
        # aiohttp doesn't seem to consistently provide close reason
        self.reason: str = ""
        self.shard_id: Optional[int] = shard_id
        super().__init__(f"Shard ID {self.shard_id} WebSocket closed with {self.code}")


def to_json(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)


class KeepAliveHandler(threading.Thread):
    def __init__(
        self,
        *args: Any,
        ws: "DiscordWebSocket",
        interval: Optional[float] = None,
        shard_id: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.ws: "DiscordWebSocket" = ws
        self._main_thread_id: int = ws.thread_id
        self.interval: Optional[float] = interval
        self.daemon: bool = True
        self.shard_id: Optional[int] = shard_id
        self.msg: str = "Keeping shard ID %s websocket alive with sequence %s."
        self.block_msg: str = "Shard ID %s heartbeat blocked for more than %s seconds."
        self.behind_msg: str = "Can't keep up, shard ID %s websocket is %.1fs behind."
        self._stop_ev: threading.Event = threading.Event()
        self._last_ack: float = time.perf_counter()
        self._last_send: float = time.perf_counter()
        self._last_recv: float = time.perf_counter()
        self.latency: float = float("inf")
        self.heartbeat_timeout: float = ws._max_heartbeat_timeout

    def run(self) -> None:
        while not self._stop_ev.wait(self.interval):
            if self._last_recv + self.heartbeat_timeout < time.perf_counter():
                log.warning(
                    "Shard ID %s has stopped responding to the gateway. Closing and restarting.",
                    self.shard_id,
                )
                coro = self.ws.close(4000)
                f = asyncio.run_coroutine_threadsafe(coro, loop=self.ws.loop)

                try:
                    f.result()
                except Exception:
                    log.exception(
                        "An error occurred while stopping the gateway. Ignoring."
                    )
                finally:
                    self.stop()
                    return

            data = self.get_payload()
            log.debug(self.msg, self.shard_id, data["d"])
            coro = self.ws.send_heartbeat(data)
            f = asyncio.run_coroutine_threadsafe(coro, loop=self.ws.loop)
            try:
                # block until sending is complete
                total = 0
                while True:
                    try:
                        f.result(10)
                        break
                    except concurrent.futures.TimeoutError:
                        total += 10
                        try:
                            frame = sys._current_frames()[self._main_thread_id]
                        except KeyError:
                            msg = self.block_msg
                        else:
                            stack = "".join(traceback.format_stack(frame))
                            msg = f"{self.block_msg}\nLoop thread traceback (most recent call last):\n{stack}"
                        log.warning(msg, self.shard_id, total)

            except Exception:
                self.stop()
            else:
                self._last_send = time.perf_counter()

    def get_payload(self) -> dict[str, Any]:
        return {
            "op": self.ws.HEARTBEAT,
            "d": self.ws.sequence,
        }

    def stop(self) -> None:
        self._stop_ev.set()

    def tick(self) -> None:
        self._last_recv = time.perf_counter()

    def ack(self) -> None:
        ack_time = time.perf_counter()
        self._last_ack = ack_time
        self.latency = ack_time - self._last_send
        if self.latency > 10:
            log.warning(self.behind_msg, self.shard_id, self.latency)


class VoiceKeepAliveHandler(KeepAliveHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.recent_ack_latencies: deque[float] = deque(maxlen=20)
        self.msg: str = "Keeping shard ID %s voice websocket alive with timestamp %s."
        self.block_msg: str = (
            "Shard ID %s voice heartbeat blocked for more than %s seconds"
        )
        self.behind_msg: str = (
            "High socket latency, shard ID %s heartbeat is %.1fs behind"
        )

    def get_payload(self) -> dict[str, Any]:
        return {
            "op": self.ws.HEARTBEAT,
            "d": int(time.time() * 1000),
        }

    def ack(self) -> None:
        ack_time = time.perf_counter()
        self._last_ack = ack_time
        self._last_recv = ack_time
        self.latency: float = ack_time - self._last_send
        self.recent_ack_latencies.append(self.latency)


class DiscordVoiceWebSocket:
    """Implements the websocket protocol for handling voice connections.
    Attributes
    -----------
    IDENTIFY
        Send only. Starts a new voice session.
    SELECT_PROTOCOL
        Send only. Tells discord what encryption mode and how to connect for voice.
    READY
        Receive only. Tells the websocket that the initial connection has completed.
    HEARTBEAT
        Send only. Keeps your websocket connection alive.
    SESSION_DESCRIPTION
        Receive only. Gives you the secret key required for voice.
    SPEAKING
        Send only. Notifies the client if you are currently speaking.
    HEARTBEAT_ACK
        Receive only. Tells you your heartbeat has been acknowledged.
    RESUME
        Sent only. Tells the client to resume its session.
    HELLO
        Receive only. Tells you that your websocket connection was acknowledged.
    RESUMED
        Sent only. Tells you that your RESUME request has succeeded.
    CLIENT_CONNECT
        Indicates a user has connected to voice.
    CLIENT_DISCONNECT
        Receive only.  Indicates a user has disconnected from voice.
    """

    if TYPE_CHECKING:
        thread_id: int
        _connection: "VoiceClient"
        gateway: str
        _max_heartbeat_timeout: float

    # fmt: off
    IDENTIFY            = 0
    SELECT_PROTOCOL     = 1
    READY               = 2
    HEARTBEAT           = 3
    SESSION_DESCRIPTION = 4
    SPEAKING            = 5
    HEARTBEAT_ACK       = 6
    RESUME              = 7
    HELLO               = 8
    RESUMED             = 9
    CLIENT_CONNECT      = 12
    CLIENT_DISCONNECT   = 13
    # fmt: on

    def __init__(
        self,
        socket: aiohttp.ClientWebSocketResponse,
        loop: asyncio.AbstractEventLoop,
        *,
        hook: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None,
    ) -> None:
        self.ws: aiohttp.ClientWebSocketResponse = socket
        self.loop: asyncio.AbstractEventLoop = loop
        self._keep_alive: Optional[Any] = None
        self._close_code: Optional[int] = None
        self.secret_key: Optional[str] = None
        if hook:
            self._hook = (
                hook  # type : ignore - type-checker doesn't like overriding methods
            )

    async def _hook(self, *args: Any) -> None:
        pass

    async def send_as_json(self, data: Any) -> None:
        log.debug("Sending voice websocket frame: %s.", data)
        await self.ws.send_str(to_json(data))

    send_heartbeat = send_as_json

    async def resume(self) -> None:
        state = self._connection
        payload = {
            "op": self.RESUME,
            "d": {
                "token": state.token,
                "server_id": str(state.server_id),
                "session_id": state.session_id,
            },
        }
        await self.send_as_json(payload)

    async def identify(self) -> None:
        state = self._connection
        payload = {
            "op": self.IDENTIFY,
            "d": {
                "server_id": str(state.server_id),
                "user_id": str(state.user.id),
                "session_id": state.session_id,
                "token": state.token,
            },
        }
        await self.send_as_json(payload)

    @classmethod
    async def from_client(
        cls,
        client: "VoiceClient",
        *,
        resume: bool = False,
        hook: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None,
    ) -> "DiscordVoiceWebSocket":
        """Creates a voice websocket for the :class:`VoiceClient`."""
        gateway = "wss://" + client.endpoint + "/?v=4"
        http = client._state.http
        socket = await http.ws_connect(gateway, compress=15)
        ws = cls(socket, loop=client.loop, hook=hook)
        ws.gateway = gateway
        ws._connection = client
        ws._max_heartbeat_timeout = 60.0
        ws.thread_id = threading.get_ident()

        if resume:
            await ws.resume()
        else:
            await ws.identify()

        return ws

    async def select_protocol(self, ip: str, port: int, mode: int) -> None:
        payload = {
            "op": self.SELECT_PROTOCOL,
            "d": {
                "protocol": "udp",
                "data": {
                    "address": ip,
                    "port": port,
                    "mode": mode,
                },
            },
        }

        await self.send_as_json(payload)

    async def client_connect(self) -> None:
        payload = {
            "op": self.CLIENT_CONNECT,
            "d": {
                "audio_ssrc": self._connection.ssrc,
            },
        }

        await self.send_as_json(payload)

    async def speak(self, state: int = 1) -> None:
        payload = {
            "op": self.SPEAKING,
            "d": {
                "speaking": int(state),
                "delay": 0,
            },
        }

        await self.send_as_json(payload)

    async def received_message(self, msg: dict[str, Any]) -> None:
        log.debug("Voice websocket frame received: %s", msg)
        op = msg["op"]
        data = msg["d"]  # According to Discord this key is always given

        if op == self.READY:
            await self.initial_connection(data)
        elif op == self.HEARTBEAT_ACK:
            if self._keep_alive:
                self._keep_alive.ack()
        elif op == self.RESUMED:
            log.info("Voice RESUME succeeded.")
        elif op == self.SESSION_DESCRIPTION:
            self._connection.mode = data["mode"]
            await self.load_secret_key(data)
        elif op == self.HELLO:
            interval = data["heartbeat_interval"] / 1000.0
            self._keep_alive = VoiceKeepAliveHandler(
                ws=self, interval=min(interval, 5.0)
            )
            self._keep_alive.start()

        await self._hook(self, msg)

    async def initial_connection(self, data: dict[str, Any]) -> None:
        state = self._connection
        state.ssrc = data["ssrc"]
        state.voice_port = data["port"]
        state.endpoint_ip = data["ip"]

        packet = bytearray(70)
        struct.pack_into(">H", packet, 0, 1)  # 1 = Send
        struct.pack_into(">H", packet, 2, 70)  # 70 = Length
        struct.pack_into(">I", packet, 4, state.ssrc)
        state.socket.sendto(packet, (state.endpoint_ip, state.voice_port))
        recv = await self.loop.sock_recv(state.socket, 70)
        log.debug("received packet in initial_connection: %s", recv)

        # the ip is ascii starting at the 4th byte and ending at the first null
        ip_start = 4
        ip_end = recv.index(0, ip_start)
        state.ip = recv[ip_start:ip_end].decode("ascii")

        state.port = struct.unpack_from(">H", recv, len(recv) - 2)[0]
        log.debug("detected ip: %s port: %s", state.ip, state.port)

        # there *should* always be at least one supported mode (xsalsa20_poly1305)
        modes = [
            mode for mode in data["modes"] if mode in self._connection.supported_modes
        ]
        log.debug("received supported encryption modes: %s", ", ".join(modes))

        mode = modes[0]
        await self.select_protocol(state.ip, state.port, mode)
        log.info("selected the voice protocol for use (%s)", mode)

    @property
    def latency(self) -> float:
        """:class:`float`: Latency between a HEARTBEAT and its HEARTBEAT_ACK in seconds."""
        heartbeat = self._keep_alive
        return float("inf") if heartbeat is None else heartbeat.latency

    @property
    def average_latency(self) -> float:
        """:class:`float`: Average of last 20 HEARTBEAT latencies."""
        heartbeat = self._keep_alive
        if heartbeat is None or not heartbeat.recent_ack_latencies:
            return float("inf")

        return sum(heartbeat.recent_ack_latencies) / len(heartbeat.recent_ack_latencies)

    async def load_secret_key(self, data: dict[str, Any]) -> None:
        log.info("received secret key for voice connection")
        self.secret_key = self._connection.secret_key = data["secret_key"]
        await self.speak()
        await self.speak(0)

    async def poll_event(self) -> None:
        # This exception is handled up the chain
        msg = await asyncio.wait_for(self.ws.receive(), timeout=30.0)
        if msg.type is aiohttp.WSMsgType.TEXT:
            await self.received_message(json.loads(msg.data))
        elif msg.type is aiohttp.WSMsgType.ERROR:
            log.debug("Received %s", msg)
            raise ConnectionClosed(self.ws, shard_id=None) from msg.data
        elif msg.type in (
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSING,
        ):
            log.debug("Received %s", msg)
            raise ConnectionClosed(self.ws, shard_id=None, code=self._close_code)

    async def close(self, code: int = 1000) -> None:
        if self._keep_alive is not None:
            self._keep_alive.stop()

        self._close_code = code
        await self.ws.close(code=code)
