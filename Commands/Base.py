import re
from typing import Generator

import discord
from discord import app_commands

from Golconda.Storage import evilsingleton

discordid = re.compile(r"<@!(\d+)>")


async def invoke(message: discord.Message):
    storage = evilsingleton()
    if message.channel.id not in storage.allowed_channels:
        storage.allowed_channels.append(message.channel.id)
        storage.write()
        await message.reply("i will now listen here, until someone banishes me.")
    await message.add_reaction("\N{THUMBS UP SIGN}")


async def banish(message: discord.Message):
    if "BANISH" in message.content:
        storage = evilsingleton()
        storage.allowed_channels.remove(message.channel.id)
        storage.write()
        await message.add_reaction("\N{THUMBS UP SIGN}")


def message_prep(message: discord.Message) -> Generator[list[str], None, None]:
    for msg in (message.content or "").split("\n"):
        msg = re.sub(r"<@[!&]?\d{18}>", "", msg).lower().strip("` ")
        storage = evilsingleton()
        selfname = storage.me.name.lower()
        if msg.lower().startswith(selfname):
            msg = msg[len(selfname) :]
        yield [x for x in msg.split() if x]


def register(tree: discord.app_commands.CommandTree):
    @tree.command(
        name="whoami",
        description="gets the currently configured NosferatuNetwork account name",
    )
    async def who_am_i(interaction: discord.Interaction):
        try:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                "You are "
                f"{evilsingleton().storage[str(interaction.user)]['NossiAccount']} \n"
                f"Your defines are: {evilsingleton().storage[str(interaction.user)]}.",
                ephemeral=True,
            )
        except KeyError:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                "You are not registered.", ephemeral=True
            )

    @app_commands.describe(say="the message that will be posted")
    @tree.command(name="anon", description="say something anonymously")
    async def anon(cmd, say: str):
        c = await cmd.fetch_channel()
        await cmd.respond_instant_ephemeral("send message anonymously")
        await c.send(f"anon: {say}")

    @app_commands.describe(nossiaccount="your name on the NosferatuNet")
    @tree.command(
        name="register", description="sets up the connection to the NosferatuNetwork"
    )
    async def i_am(interaction: discord.Interaction, nossiaccount: str):
        s = evilsingleton()
        d = s.storage.setdefault(str(interaction.user), {"defines": {}})
        if not nossiaccount:
            d.pop("NossiAccount")
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("... Who are you?", ephemeral=True)
        else:
            d["NossiAccount"] = nossiaccount.upper()
            d["DiscordAccount"] = str(interaction.user)
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                f"I have saved your account as {d['NossiAccount']}.", ephemeral=True
            )
        s.write()
