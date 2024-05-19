import discord.app_commands
from typing import Callable, Awaitable

from Commands import Char, Oracle, Voice, Base, Wiki, Remind

callbacks: dict[str : Callable[[discord.Interaction], Awaitable]] = {}


def register(tree: discord.app_commands.CommandTree):
    Char.register(tree, callbacks)
    Oracle.register(tree)
    Voice.register(tree)
    Base.register(tree)
    Wiki.register(tree)
    Remind.register(tree)


async def route(event: discord.Interaction, custom_id: str):
    for key, callback in callbacks.items():
        if custom_id.startswith(key):
            await callback(event)
