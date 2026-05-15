import logging
from typing import Optional

from Commands.Base import message_prep, BaseCommand, invoke
from Commands.Oracle import OracleCommand
from Commands.Char import CharCommand
from Commands.Roll import RollCommand
from Commands.Remind import RemindCommand
from Commands.Wiki import WikiCommand
from Commands.Minecraft import MinecraftCommand
from Commands.Voice import VoiceCommand
from Golconda.EasterEggs import eastereggs
from Golconda.RollInterface import rollhandle, AuthorError
from Golconda.Storage import evilsingleton
from Golconda.Tools import get_remembering_send

logger = logging.getLogger(__name__)

COMMAND_REGISTRY = {
    "oracle": OracleCommand,
    "char": CharCommand,
    "r": RollCommand,
    "roll": RollCommand,
    "remind": RemindCommand,
    "wiki": WikiCommand,
    "minecraft": MinecraftCommand,
    "voice": VoiceCommand,
    "whoami": BaseCommand,
    "register": BaseCommand,
    "anon": BaseCommand,
    "list": BaseCommand,
    "invoke": BaseCommand,
    "banish": BaseCommand,
    "die": BaseCommand,
    "make": BaseCommand,
    "def": BaseCommand,
    "undef": BaseCommand,
}


async def help_system(ctx, query: Optional[str] = None) -> None:
    if not query or query.lower() == "okysa":
        lines = [
            "**Okysa Bot Help**",
            "I'm a multi-platform RPG utility bot.",
            "Available commands:",
        ]
        seen_commands = set()
        for name, cmd_class in COMMAND_REGISTRY.items():
            if cmd_class in seen_commands:
                continue
            seen_commands.add(cmd_class)
            doc = cmd_class.__doc__ or "No description available."
            first_line = doc.split("\n")[0].strip()
            lines.append(f"- `{name}`: {first_line}")

        lines.append("\nUse `?<command>` for specific help (e.g., `?oracle`).")
        lines.append("Use `?<command> <subcommand>` for detailed parameter info.")
        await ctx.reply("\n".join(lines))
        return

    parts = query.split()
    cmd_name = parts[0].lower()
    sub_name = parts[1].lower() if len(parts) > 1 else None

    if cmd_name not in COMMAND_REGISTRY:
        await ctx.reply(f"No help available for command: {cmd_name}")
        return

    cmd_class = COMMAND_REGISTRY[cmd_name]
    if sub_name:
        method = getattr(cmd_class, f"{sub_name}_logic", None)
        if method and method.__doc__:
            await ctx.reply(
                f"**{cmd_name.capitalize()} {sub_name} Help**\n{method.__doc__.strip()}"
            )
            return
        doc = cmd_class.__doc__ if cmd_class.__doc__ else "No description available."
        await ctx.reply(f"Showing `{cmd_name}` help:\n{doc.strip()}")
    else:
        doc = cmd_class.__doc__ if cmd_class.__doc__ else "No description available."
        await ctx.reply(f"**{cmd_name.capitalize()} Help**\n{doc.strip()}")


async def main_route(ctx) -> None:
    """Route a message to the appropriate command."""
    s = evilsingleton()
    message = ctx.message
    content = message.content or ""

    if content.startswith("?"):
        query = content[1:].strip()
        parts = query.split()
        if not query or (parts and parts[0].lower() in COMMAND_REGISTRY):
            await help_system(ctx, query)
            return

    for m in message_prep(content):
        if not m:
            continue
        cmd = m[0].lower()

        if cmd in COMMAND_REGISTRY:
            handler = COMMAND_REGISTRY[cmd]
            if hasattr(handler, "handle"):
                await handler.handle(ctx, m)
                continue

        match m:
            case [mention, "invoke"] if str(mention) == str(ctx.bot_user.mention):
                await invoke(message)
            case roll:
                msg = " ".join(roll)
                mention = ctx.author.mention
                try:
                    if (
                        await rollhandle(
                            msg,
                            mention,
                            get_remembering_send(message),
                            message.add_reaction,
                            s.storage,
                        )
                        is None
                    ):
                        await eastereggs(message)
                except AuthorError as e:
                    await ctx.author.send(e.args[0])
