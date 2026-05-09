from dataclasses import dataclass, field
from typing import Protocol, Any, Optional, runtime_checkable


@runtime_checkable
class BotCommand(Protocol):
    """Protocol for Okysa commands."""

    @staticmethod
    async def handle(ctx: "BotContext", args: list[str]) -> None:
        """Handle a command or subcommand dispatching."""
        ...


class BotUser(Protocol):
    id: str
    name: str
    display_name: str
    mention: str

    def __str__(self) -> str:
        """Return the unique identifier or name as a string."""
        ...


class BotChannel(Protocol):
    id: str
    name: str

    async def send(self, content: str, **kwargs) -> Any:
        """Send a message to this channel."""
        ...


class BotMessage(Protocol):
    id: str
    content: str
    author: BotUser
    channel: BotChannel
    guild_id: Optional[str]
    guild_owner_id: Optional[str]  # New: abstracted guild owner
    mentions: list[BotUser]
    role_mentions: list[str] = field(
        default_factory=list
    )  # New: IDs of mentioned roles
    reply_to_id: Optional[str] = field(default=None)  # New: Abstracted reply reference

    async def reply(self, content: str, **kwargs) -> Any:
        """Reply to this message."""
        ...

    async def add_reaction(self, emoji: str) -> None:
        """Add a reaction to this message."""
        ...


@dataclass
class BotContext:
    message: BotMessage
    platform: str  # "discord" or "matrix"
    bot_user: BotUser
    owner_id: str  # New: abstracted bot owner ID

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
        """Check if author is the bot owner."""
        return str(self.author.id) == str(self.owner_id)

    def is_guild_owner(self) -> bool:
        """Check if author is the guild owner."""
        if self.message.guild_owner_id:
            return str(self.author.id) == str(self.message.guild_owner_id)
        # Fallback for DM: if bot owner, it's effectively a guild owner of their own DM
        return self.is_owner()

    def is_allowed(self) -> bool:
        """Check if the bot is allowed to respond to this context."""
        from Golconda.Storage import evilsingleton

        s = evilsingleton()

        # 1. Allowed channels
        if str(self.channel.id) in s.allowed_channels:
            return True

        # 2. DMs
        if self.message.guild_id is None:
            return True

        # 3. Mention check
        if any(str(u.id) == str(self.bot_user.id) for u in self.message.mentions):
            return True

        # 4. Role mention (abstracted)
        if hasattr(s, "getroles"):
            roles = s.getroles(self.message.guild_id)
            if roles and any(str(r.id) in self.message.role_mentions for r in roles):
                return True

        # 5. Name prefix
        return (
            (self.message.content or "")
            .strip()
            .lower()
            .startswith(str(self.bot_user.name).lower())
        )

    def is_poweruser(self) -> bool:
        """Check if author is a Minecraft poweruser."""
        from Golconda.Storage import evilsingleton

        s = evilsingleton()
        registered = s.storage.get("mc_powerusers", [])
        return int(self.author.id) in registered

    def is_dm(self) -> bool:
        """Check if the context is a Direct Message."""
        return self.message.guild_id is None
