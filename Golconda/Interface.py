from dataclasses import dataclass
from typing import Protocol, Any, Optional, runtime_checkable


@runtime_checkable
class BotCommand(Protocol):
    @staticmethod
    async def handle(ctx: "BotContext", args: list[str]) -> None:
        pass


class BotUser(Protocol):
    id: str
    name: str
    display_name: str
    mention: str

    def __str__(self) -> str:
        pass


class BotChannel(Protocol):
    id: str
    name: str

    async def send(self, content: str, **kwargs) -> Any:
        pass


class BotMessage(Protocol):
    id: str
    content: str
    author: BotUser
    channel: BotChannel
    guild_id: Optional[str]
    guild_owner_id: Optional[str]
    mentions: list[BotUser]
    role_mentions: list[str]
    reply_to_id: Optional[str]

    async def reply(self, content: str, **kwargs) -> Any:
        pass

    async def add_reaction(self, emoji: str) -> None:
        pass


@dataclass
class BotContext:
    message: BotMessage
    platform: str
    bot_user: BotUser
    owner_id: str

    @property
    def author(self) -> BotUser:
        return self.message.author

    @property
    def channel(self) -> BotChannel:
        return self.message.channel

    async def reply(self, content: str, **kwargs) -> Any:
        return await self.message.reply(content, **kwargs)

    async def send(self, content: str, **kwargs) -> Any:
        return await self.message.channel.send(content, **kwargs)

    def is_owner(self) -> bool:
        return str(self.author.id) == str(self.owner_id)

    def is_guild_owner(self) -> bool:
        if self.message.guild_owner_id:
            return str(self.author.id) == str(self.message.guild_owner_id)
        return self.is_owner()

    def is_allowed(self) -> bool:
        from Golconda.Rights import allowed

        if allowed(self.message):
            return True

        if (
            (self.message.content or "")
            .strip()
            .lower()
            .startswith(str(self.bot_user.name).lower())
        ):
            return True

        return False

    def is_poweruser(self) -> bool:
        from Golconda.Storage import evilsingleton

        s = evilsingleton()
        registered = s.storage.get("mc_powerusers", [])
        return int(self.author.id) in registered

    def is_dm(self) -> bool:
        return self.message.guild_id is None
