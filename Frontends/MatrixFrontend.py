import os
import logging
import asyncio
from typing import Any, Optional

#### python3.14 compatibility fixes ####
import nio
import nio.responses

# Restore removed asyncio.coroutine for library compatibility
if not hasattr(asyncio, "coroutine"):
    asyncio.coroutine = lambda x: x

# Bulletproof nio SyncResponse to avoid KeyError crashes on 3.14
original_from_dict = nio.responses.SyncResponse.from_dict


def patched_from_dict(cls, parsed_dict, *args, **kwargs):
    try:
        if "rooms" in parsed_dict:
            for section in ["join", "leave"]:
                for room_id, room_dict in parsed_dict["rooms"].get(section, {}).items():
                    for key in ["state", "timeline", "ephemeral", "account_data"]:
                        if key not in room_dict:
                            room_dict[key] = {"events": []}
                        if key == "timeline":
                            if "limited" not in room_dict[key]:
                                room_dict[key]["limited"] = False
        return original_from_dict(parsed_dict, *args, **kwargs)
    except Exception as e:
        # Keep the sync loop alive even if parsing fails
        return nio.responses.SyncResponse(
            next_batch=parsed_dict.get("next_batch", ""),
            rooms=nio.responses.Rooms({}, {}, {}),
            device_one_time_keys_count=nio.responses.DeviceOneTimeKeyCount(0, 0),
            device_lists=nio.responses.DeviceList([], []),
            to_device=nio.responses.ToDeviceResponse([]),
            presence_events=[],
            account_data=[],
        )


nio.responses.SyncResponse.from_dict = classmethod(patched_from_dict)
#########################################

try:
    import simplematrixbotlib as botlib
    from nio import InviteMemberEvent, RoomMemberEvent
except ImportError:
    botlib = None
    InviteMemberEvent = None
    RoomMemberEvent = None

from Golconda.Interface import BotUser, BotChannel, BotMessage, BotContext
from Golconda.Routing import main_route
from Golconda.Rights import allowed

logger = logging.getLogger("matrix")


class MatrixUserWrapper:
    def __init__(self, user_id: str, display_name: Optional[str] = None):
        self.id = user_id
        self.name = user_id
        self.display_name = display_name or user_id
        self.mention = user_id

    def __str__(self) -> str:
        return self.id


class MatrixChannelWrapper:
    def __init__(self, bot: botlib.Bot, room_id: str):
        self._bot = bot
        self.id = room_id
        self.name = room_id

    async def send(self, content: str, **kwargs) -> Any:
        return await self._bot.api.send_markdown_message(self.id, content)


class MatrixMessageWrapper:
    def __init__(self, bot: botlib.Bot, room_id: str, event: Any):
        self._bot = bot
        self._event = event
        self.id = str(event.event_id)
        self.content = event.body
        self.author = MatrixUserWrapper(event.sender)
        self.channel = MatrixChannelWrapper(bot, room_id)
        self.guild_id = None
        self.guild_owner_id = None
        self.mentions = []
        self.role_mentions = []

        # Matrix reply detection
        content = getattr(event, "source", {}).get("content", {})
        relates_to = content.get("m.relates_to", {})
        self.reply_to_id = relates_to.get("m.in_reply_to", {}).get("event_id")

        # Simple mention detection for Matrix (very basic)
        if self.content:
            # Check if bot's name or ID is in the content
            # This is a bit naive but standard for basic Matrix bots
            if bot.creds.username in self.content:
                self.mentions.append(MatrixUserWrapper(bot.creds.username))

    async def reply(self, content: str, **kwargs) -> Any:
        return await self._bot.api.send_markdown_message(self.channel.id, content)

    async def add_reaction(self, emoji: str) -> None:
        await self._bot.api.send_reaction(self.channel.id, self._event, emoji)


class MatrixBot:
    def __init__(self, server: str, username: str, password: str):
        if botlib is None:
            raise ImportError("simplematrixbotlib is not installed")
        self.creds = botlib.Creds(server, username, password)
        self.bot = botlib.Bot(self.creds)
        self.user = MatrixUserWrapper(f"@{username}:{server.split('://')[-1]}")
        logger.info(f"MatrixBot initialized as {self.user.id}")

        @self.bot.listener.on_startup
        async def on_startup(room=None):
            logger.info(f"MatrixBot startup triggered. Identity: {self.user.id}")

        if InviteMemberEvent:

            @self.bot.listener.on_custom_event(InviteMemberEvent)
            async def on_invite(room, event):
                logger.info(
                    f"Received invite for room {room.room_id} from {event.sender}"
                )
                matrix_owner = os.getenv("MATRIX_OWNER")
                if matrix_owner and event.sender != matrix_owner:
                    logger.warning(
                        f"Rejected invite from {event.sender} (owner is {matrix_owner})"
                    )
                    return
                await self.bot.api.join_room(room.room_id)
                logger.info(f"Accepted invite to {room.room_id}")

        if RoomMemberEvent:

            @self.bot.listener.on_custom_event(RoomMemberEvent)
            async def on_room_member(room, event):
                if event.membership == "join" and event.state_key == self.user.id:
                    logger.info(
                        f"Bot joined room {room.room_id}, sending welcome message..."
                    )
                    await self.bot.api.send_text_message(
                        room.room_id,
                        "Okysa has joined the room! I am online and ready.",
                    )

        @self.bot.listener.on_message_event
        async def on_message(room, event):
            if event.sender == self.user.id:
                return

            wrapped_message = MatrixMessageWrapper(self.bot, room.room_id, event)
            ctx = BotContext(
                message=wrapped_message,
                platform="matrix",
                bot_user=self.user,
                owner_id=os.getenv("MATRIX_OWNER", ""),
            )

            if ctx.is_allowed():
                if event.body.strip().lower() == "!ping":
                    await wrapped_message.reply("Pong! Matrix frontend is active.")
                await main_route(ctx)

    async def run(self):
        logger.info("MatrixBot starting main loop")
        asyncio.create_task(self.status_check())
        await self.bot.main()

    async def status_check(self):
        welcomed_rooms = set()
        while True:
            try:
                if self.bot.api.async_client:
                    resp = await self.bot.api.async_client.joined_rooms()
                    if hasattr(resp, "rooms"):
                        rooms = resp.rooms
                        for room_id in rooms:
                            if room_id not in welcomed_rooms:
                                logger.info(
                                    f"Matrix: Sending startup heartbeat to {room_id}"
                                )
                                await self.bot.api.send_text_message(
                                    room_id,
                                    "Okysa is online and listening. (Heartbeat)",
                                )
                                welcomed_rooms.add(room_id)
                else:
                    logger.warning("Matrix Status: async_client is None!")
            except Exception as e:
                logger.error(f"Matrix Status Check Error: {e}")
            await asyncio.sleep(60)
