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
import logging
import socket
from typing import TypeVar, Iterable, Awaitable, Optional, Mapping, Type, Any, Callable

import hikari.channels
from hikari import snowflakes, guilds, channels, UNDEFINED
from hikari.api import VoiceComponent, VoiceConnection
from hikari.events import voice_events

from Golconda.DiscordVoiceWebsocket import DiscordVoiceWebSocket, ConnectionClosed

log = logging.Logger("VoiceComponent")
_T = TypeVar("_T")
_VoiceConnectionT = TypeVar("_VoiceConnectionT", bound="VoiceConnection")


async def sane_wait_for(
    futures: Iterable[Awaitable[_T]], *, timeout: Optional[float]
) -> set[asyncio.Task[_T]]:
    ensured = [asyncio.ensure_future(fut) for fut in futures]
    done, pending = await asyncio.wait(
        ensured, timeout=timeout, return_when=asyncio.ALL_COMPLETED
    )

    if len(pending) != 0:
        raise asyncio.TimeoutError()

    return done


class TestVoiceComponent(VoiceComponent):
    def __init__(self, bot: hikari.GatewayBot):
        self.bot = bot
        self._connections: dict[snowflakes.Snowflake, VoiceConnection] = {}

    @property
    def is_alive(self) -> bool:
        return True

    @property
    def connections(self) -> Mapping[snowflakes.Snowflake, VoiceConnection]:
        return self._connections

    async def close(self) -> None:
        await self.disconnect_all()

    async def disconnect(
        self, guild: snowflakes.SnowflakeishOr[guilds.PartialGuild]
    ) -> None:
        await self._connections[guild].disconnect()

    async def disconnect_all(self) -> None:
        for connection in self._connections.values():
            await connection.disconnect()
        self._connections = {}

    async def connect_to(
        self,
        guild: snowflakes.SnowflakeishOr[guilds.Guild],
        channel: snowflakes.SnowflakeishOr[channels.GuildVoiceChannel],
        voice_connection_type: Type[_VoiceConnectionT],
        *,
        deaf: bool = False,
        mute: bool = False,
        **kwargs: Any
    ) -> _VoiceConnectionT:
        return await voice_connection_type.initialize(
            channel,
            "?",
            guild,
            lambda x: self._connections.pop(x),
            self,
            "1",
            1,
            "toke",
            kwargs["user"],
        )


class TestVoiceConnection(VoiceConnection):
    @classmethod
    async def initialize(
        cls: Type[_T],
        channel_id: snowflakes.Snowflake,
        endpoint: str,
        guild_id: snowflakes.Snowflake,
        on_close: Callable[[_T], Awaitable[None]],
        owner: VoiceComponent,
        session_id: str,
        shard_id: int,
        token: str,
        user_id: snowflakes.Snowflake,
        **kwargs: Any
    ) -> _T:
        self = cls(guild_id, channel_id, shard_id, owner, session_id, token)
        self.channel = self.owner.bot.cache.get_guild_channel(self._channel_id)
        self.guild = self.owner.bot.cache.get_guild(self._guild_id)
        return self

    def __init__(
        self,
        guild_id: snowflakes.Snowflake,
        channel_id: snowflakes.Snowflake,
        shard_id: int,
        owner: TestVoiceComponent,
        session_id: str,
        token: str,
    ):
        self.channel: hikari.channels.GuildVoiceChannel | UNDEFINED = UNDEFINED
        self.guild: hikari.Guild | UNDEFINED = UNDEFINED
        self._runner = UNDEFINED
        self._connections = 0
        self.ws: DiscordVoiceWebSocket | UNDEFINED = UNDEFINED
        self.socket: DiscordVoiceWebSocket | UNDEFINED = UNDEFINED
        self.endpoint_ip = UNDEFINED
        self.endpoint = UNDEFINED
        self.token = token
        self._potentially_reconnecting = False
        self._handshaking = True
        self._guild_id = guild_id
        self._channel_id = channel_id
        self._shard_id = shard_id
        self._owner = owner
        self.session_id = session_id
        self._voice_state_complete: asyncio.Event = asyncio.Event()
        self._voice_server_complete: asyncio.Event = asyncio.Event()
        self._connected = asyncio.Event = asyncio.Event()

    async def join(self) -> None:
        await self.voice_connect()

    @property
    def channel_id(self) -> snowflakes.Snowflake:
        return self._channel_id

    @property
    def guild_id(self) -> snowflakes.Snowflake:
        return self._guild_id

    @property
    def is_alive(self) -> bool:
        return True

    @property
    def shard_id(self) -> int:
        return self._shard_id

    @property
    def owner(self) -> TestVoiceComponent:
        return self._owner

    async def notify(self, event: voice_events.VoiceEvent) -> None:
        if isinstance(event, voice_events.VoiceStateUpdateEvent):
            await self.on_voice_state_update(event)

    async def on_voice_state_update(
        self, event: voice_events.VoiceStateUpdateEvent
    ) -> None:
        self.session_id: str = event.state.session_id
        channel_id = event.state.guild_id

        if not self._handshaking or self._potentially_reconnecting:
            # If we're done handshaking then we just need to update ourselves
            # If we're potentially reconnecting due to a 4014, then we need to differentiate
            # a channel move and an actual force disconnect
            if channel_id is None:
                # We're being disconnected so cleanup
                await self.disconnect()
            else:
                self._channel_id = channel_id
                # type : ignore - this won't be None
        else:
            self._voice_state_complete.set()

    async def on_voice_server_update(
        self, event: voice_events.VoiceServerUpdateEvent
    ) -> None:
        if self._voice_server_complete.is_set():
            # already have a voice server
            return

        self.token = event.token
        self._guild_id = int(event.guild_id)
        endpoint = event.endpoint

        if endpoint is None or self.token is None:
            # wait needed
            return

        self.endpoint, _, _ = endpoint.rpartition(":")
        # This gets set later
        self.endpoint_ip = UNDEFINED

        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)

        if not self._handshaking:
            # If we're not handshaking then we need to terminate our previous connection in the websocket
            await self.ws.close(4000)
            return

        self._voice_server_complete.set()

    async def voice_connect(self) -> None:
        await self.ws

    async def voice_disconnect(self) -> None:
        log.info(
            "The voice handshake is being terminated for Channel ID %s (Guild ID %s)",
            self.channel.id,
            self.guild.id,
        )
        await self.channel.guild.change_voice_state(channel=None)

    def prepare_handshake(self) -> None:
        self._voice_state_complete.clear()
        self._voice_server_complete.clear()
        self._handshaking = True
        log.info(
            "Starting voice handshake... (connection attempt %d)", self._connections + 1
        )
        self._connections += 1

    def finish_handshake(self) -> None:
        log.info("Voice handshake complete. Endpoint found %s", self.endpoint)
        self._handshaking = False
        self._voice_server_complete.clear()
        self._voice_state_complete.clear()

    async def connect_websocket(self) -> DiscordVoiceWebSocket:
        ws = await DiscordVoiceWebSocket.from_client(self)
        self._connected.clear()
        while ws.secret_key is None:
            await ws.poll_event()
        self._connected.set()
        return ws

    async def connect(self, *, reconnect: bool, timeout: float) -> None:
        log.info("Connecting to voice...")
        for i in range(5):
            self.prepare_handshake()

            # This has to be created before we start the flow.
            futures = [
                self._voice_state_complete.wait(),
                self._voice_server_complete.wait(),
            ]

            # Start the connection flow
            await self.voice_connect()

            try:
                await sane_wait_for(futures, timeout=timeout)
            except asyncio.TimeoutError:
                await self.disconnect(force=True)
                raise

            self.finish_handshake()

            try:
                self.ws = await self.connect_websocket()
                break
            except (ConnectionClosed, asyncio.TimeoutError):
                if reconnect:
                    log.exception("Failed to connect to voice... Retrying...")
                    await asyncio.sleep(1 + i * 2.0)
                    await self.voice_disconnect()
                    continue
                else:
                    raise

        if self._runner is UNDEFINED:
            self._runner = asyncio.get_running_loop().create_task(
                self.poll_voice_ws(reconnect)
            )

    async def potential_reconnect(self) -> bool:
        # Attempt to stop the player thread from playing early
        self._connected.clear()
        self.prepare_handshake()
        self._potentially_reconnecting = True
        try:
            # We only care about VOICE_SERVER_UPDATE since VOICE_STATE_UPDATE can come before we get disconnected
            await asyncio.wait_for(self._voice_server_complete.wait(), timeout=15)
        except asyncio.TimeoutError:
            self._potentially_reconnecting = False
            await self.disconnect(force=True)
            return False

        self.finish_handshake()
        self._potentially_reconnecting = False
        try:
            self.ws = await self.connect_websocket()
        except (ConnectionClosed, asyncio.TimeoutError):
            return False
        else:
            return True

    @property
    def latency(self) -> float:
        """:class:`float`: Latency between a HEARTBEAT and a HEARTBEAT_ACK in seconds.
        This could be referred to as the Discord Voice WebSocket latency and is
        an analogue of user's voice latencies as seen in the Discord client.
        .. versionadded:: 1.4
        """
        ws = self.ws
        return float("inf") if not ws else ws.latency

    @property
    def average_latency(self) -> float:
        """:class:`float`: Average of most recent 20 HEARTBEAT latencies in seconds.
        .. versionadded:: 1.4
        """
        ws = self.ws
        return float("inf") if not ws else ws.average_latency

    async def poll_voice_ws(self, reconnect: bool) -> None:
        while True:
            try:
                await self.ws.poll_event()
            except (ConnectionClosed, asyncio.TimeoutError) as exc:
                if isinstance(exc, ConnectionClosed):
                    # The following close codes are undocumented so I will document them here.
                    # 1000 - normal closure (obviously)
                    # 4014 - voice channel has been deleted.
                    # 4015 - voice server has crashed
                    if exc.code in (1000, 4015):
                        log.info(
                            "Disconnecting from voice normally, close code %d.",
                            exc.code,
                        )
                        await self.disconnect()
                        break
                    if exc.code == 4014:
                        log.info(
                            "Disconnected from voice by force... potentially reconnecting."
                        )
                        successful = await self.potential_reconnect()
                        if not successful:
                            log.info(
                                "Reconnect was unsuccessful, disconnecting from voice normally..."
                            )
                            await self.disconnect()
                            break
                        else:
                            continue

                if not reconnect:
                    await self.disconnect()
                    raise

                retry = 15
                log.exception(
                    "Disconnected from voice... Reconnecting in %.2fs.", retry
                )
                self._connected.clear()
                await asyncio.sleep(retry)
                await self.voice_disconnect()
                try:
                    await self.connect(reconnect=True, timeout=15)
                except asyncio.TimeoutError:
                    # at this point we've retried 5 times... let's continue the loop.
                    log.warning("Could not connect to voice... Retrying...")
                    continue

    async def disconnect(self, *, force: bool = False) -> None:
        """|coro|
        Disconnects this voice client from voice.
        """
        if not force and not self.is_connected():
            return
        self._connected.clear()

        try:
            if self.ws:
                await self.ws.close()

            await self.voice_disconnect()
        finally:
            self.cleanup()
            if self.socket:
                await self.socket.close()

    def is_connected(self) -> bool:
        return self._connected.is_set()

    def cleanup(self) -> None:
        """This method *must* be called to ensure proper clean-up during a disconnect.
        It is advisable to call this from within :meth:`disconnect` when you are
        completely done with the voice protocol instance.
        This method removes it from the internal state cache that keeps track of
        currently alive voice clients. Failure to clean-up will cause subsequent
        connections to report that it's still connected.
        """
        # key_id, _ = self.channel._get_voice_client_key()
        # self.client._connection._remove_voice_client(key_id)
