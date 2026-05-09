import logging
import re
from typing import Any, Optional, Dict, Callable

from Commands.Base import message_prep, banish, invoke, make_bridge, BaseCommand
from Commands.Oracle import OracleCommand
from Commands.Char import CharCommand
from Commands.Roll import RollCommand
from Commands.Remind import RemindCommand
from Commands.Wiki import WikiCommand
from Commands.Minecraft import MinecraftCommand
from Commands.Voice import VoiceCommand
from Golconda.EasterEggs import eastereggs
from Golconda.Rights import is_owner
from Golconda.RollInterface import rollhandle, AuthorError
from Golconda.Storage import evilsingleton
from Golconda.Tools import (
    define,
    undefine,
    get_remembering_send,
)

logger = logging.getLogger(__name__)

# Agnostic command registry
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
        # General help list synthesized from class docstrings
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
        # Try to find a method ending in _logic for the subcommand
        method = getattr(cmd_class, f"{sub_name}_logic", None)
        if method and method.__doc__:
            await ctx.reply(
                f"**{cmd_name.capitalize()} {sub_name} Help**\n{method.__doc__.strip()}"
            )
            return
        # If no specific method doc, just show class doc
        await ctx.reply(
            f"Showing `{cmd_name}` help:\n{cmd_class.__doc__.strip() if cmd_class.__doc__ else 'No description available.'}"
        )
    else:
        await ctx.reply(
            f"**{cmd_name.capitalize()} Help**\n{cmd_class.__doc__.strip() if cmd_class.__doc__ else 'No description available.'}"
        )


async def main_route(ctx) -> None:
    """Route a message to the appropriate command."""
    s = evilsingleton()
    message = ctx.message
    content = message.content or ""

    # 1. Help System / Diagnosis Handling (?)
    if content.startswith("?"):
        query = content[1:].strip()
        parts = query.split()
        # If it's just '?' or '?<command>', show help.
        # Otherwise, fall through to roll diagnosis.
        if not query or (parts and parts[0].lower() in COMMAND_REGISTRY):
            await help_system(ctx, query)
            return

    # 2. Legacy / Agnostic Dispatching
    for m in message_prep(content):
        if not m:
            continue
        cmd = m[0].lower()

        # Handle Agnostic Commands (Prefix-less for Matrix, or mentioned for Discord)
        if cmd in COMMAND_REGISTRY:
            handler = COMMAND_REGISTRY[cmd]
            if hasattr(handler, "handle"):
                await handler.handle(ctx, m)
                continue

        match m:
            case [mention, "invoke"] if str(mention) == str(ctx.bot_user.mention):
                # Mention based invoke still here as it's special
                from Commands.Base import invoke

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
