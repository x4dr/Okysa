import discord
from discord import app_commands
from typing import Any
from datetime import datetime
import logging

from Golconda.Interface import BotContext
from Golconda.Routing import main_route
from Golconda.Storage import setup, migrate, evilsingleton
from Golconda.Clocks import clockhandle
from Golconda.Scheduling import periodic
from Golconda.Rights import allowed

logger = logging.getLogger("discord")


class DiscordUserWrapper:
    def __init__(self, user: discord.User | discord.Member):
        self._user = user
        self.id = str(user.id)
        self.name = user.name
        self.display_name = getattr(user, "display_name", user.name)
        self.mention = user.mention

    def __str__(self) -> str:
        return str(self._user)


class DiscordChannelWrapper:
    def __init__(self, channel: discord.abc.Messageable):
        self._channel = channel
        self.id = str(channel.id)
        self.name = getattr(channel, "name", "DM")

    async def send(self, content: str, **kwargs) -> Any:
        return await self._channel.send(content, **kwargs)


class DiscordMessageWrapper:
    def __init__(self, message: discord.Message):
        self._message = message
        self.id = str(message.id)
        self.content = message.content
        self.author = DiscordUserWrapper(message.author)
        self.channel = DiscordChannelWrapper(message.channel)
        self.guild_id = str(message.guild.id) if message.guild else None
        self.guild_owner_id = str(message.guild.owner_id) if message.guild else None
        self.mentions = [DiscordUserWrapper(u) for u in message.mentions]
        self.role_mentions = (
            [str(r.id) for r in message.role_mentions]
            if hasattr(message, "role_mentions")
            else []
        )
        self.reply_to_id = (
            str(message.reference.message_id) if message.reference else None
        )

    async def reply(self, content: str, **kwargs) -> Any:
        return await self._message.reply(content, **kwargs)

    async def add_reaction(self, emoji: str) -> None:
        await self._message.add_reaction(emoji)


class DiscordBot(discord.Client):
    def __init__(self, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self) -> None:
        await setup(self)
        if self.application and self.application.owner:
            await self.application.owner.send(f"I am {self.user} (Discord)!")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"prayers since {datetime.now().strftime('%H:%M %d.%m.%Y')}",
            )
        )
        await clockhandle()
        await periodic()

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return

        # Wrap the message
        wrapped_message = DiscordMessageWrapper(message)
        ctx = BotContext(
            message=wrapped_message,
            platform="discord",
            bot_user=DiscordUserWrapper(self.user),
            owner_id=(
                str(self.application.owner.id)
                if self.application and self.application.owner
                else ""
            ),
        )

        # Legacy bridge handling
        if str(message.channel.id) == str(evilsingleton().bridge_channel):
            evilsingleton().store_message(message)

        if ctx.is_allowed():
            await main_route(ctx)

            # Legacy treesync
            if (
                "treesync" in message.content
                and hasattr(self.application, "owner")
                and self.application.owner == message.author
            ):
                msg = ""
                for c in await self.tree.sync():
                    msg += c.name + "\n"
                await message.channel.send(content=msg)

        await migrate(self, DiscordUserWrapper(message.author))
        for user in message.mentions:
            await migrate(self, DiscordUserWrapper(user))

    async def on_raw_message_edit(self, event: discord.RawMessageUpdateEvent) -> None:
        channel = self.get_channel(event.channel_id)
        if isinstance(channel, discord.abc.Messageable):
            try:
                message = await channel.fetch_message(event.message_id)
                if message.author == self.user:
                    return

                wrapped_message = DiscordMessageWrapper(message)
                if not await allowed(wrapped_message):
                    return

                ctx = BotContext(
                    message=wrapped_message,
                    platform="discord",
                    bot_user=DiscordUserWrapper(self.user),
                )
                await main_route(ctx)
            except discord.NotFound:
                pass

    async def on_raw_message_delete(self, event: discord.RawMessageDeleteEvent) -> None:
        channel = self.get_channel(event.channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return

        # This part is a bit tricky since we don't have the message content anymore
        # but we can try to find the bot's reply
        # (Simplified version of the original logic)
        message = channel.get_partial_message(event.message_id)
        d = 0.5
        if hasattr(channel, "history"):
            async for m in channel.history(limit=10):
                if (
                    m.author == self.user
                    and m.reference
                    and m.reference.message_id == message.id
                ):
                    await m.delete(delay=d)
                    d += 0.5
