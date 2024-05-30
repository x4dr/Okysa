import discord.app_commands

from Commands import Char, Oracle, Voice, Base, Wiki, Remind, Roll


def register(tree: discord.app_commands.CommandTree):
    Char.register(tree)
    Oracle.register(tree)
    Voice.register(tree)
    Base.register(tree)
    Wiki.register(tree)
    Remind.register(tree)
    Roll.register(tree)
