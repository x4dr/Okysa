import re
from typing import Generator

import discord
from discord import app_commands

from Golconda import Rights
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


def message_prep(message: str) -> Generator[list[str], None, None]:
    storage = evilsingleton()
    selfname = storage.me.name.lower()
    for msg in (message or "").split("\n"):
        msg = msg.lower().strip("` ")
        if msg.lower().startswith(selfname):
            msg = msg[len(selfname) :]
        yield [x for x in msg.split() if x]


async def make_bridge(message: discord.Message):
    if Rights.is_owner(message.author):
        storage = evilsingleton()
        evilsingleton().bridge_channel = message.channel.id
        storage.save_conf("bridge", "channelid", str(message.channel.id))
        storage.save_conf(
            "bridge",
            "webhook",
            (await message.channel.create_webhook(name="NosferatuBridge")).url,
        )
        storage.write()
        await message.add_reaction("\N{LINK SYMBOL}")
        return True
    return False


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
                f"{evilsingleton().storage[str(interaction.user.id)]['NossiAccount']} \n"
                f"Your data is: {evilsingleton().storage[str(interaction.user.id)]}.",
                ephemeral=True,
            )
        except KeyError:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                "You are not registered.", ephemeral=True
            )

    @app_commands.describe(say="the message that will be posted")
    @tree.command(name="anon", description="say something anonymously")
    async def anon(interaction: discord.Interaction, say: str):
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("message sent", ephemeral=True)
        await interaction.channel.send(f"anon: {say}")

    @app_commands.describe(nossiaccount="your name on the NosferatuNet")
    @tree.command(
        name="register", description="sets up the connection to the NosferatuNetwork"
    )
    async def i_am(interaction: discord.Interaction, nossiaccount: str):
        s = evilsingleton()
        d: dict[str, str | dict] = s.storage.setdefault(
            str(interaction.user.id), {"defines": {}}
        )
        if not nossiaccount:
            d.pop("NossiAccount")
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("... Who are you?", ephemeral=True)
        else:
            d["NossiAccount"] = nossiaccount.upper()
            d["DiscordAccount"] = str(interaction.user.id)
            s.save_conf(
                d["NossiAccount"],
                "unconfirmed_discord_link",
                d["DiscordAccount"] + "(" + interaction.user.name + ")",
            )
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                f"I have saved your account as {d['NossiAccount']}.\n"
                f"go to https://{s.nossilink}/config/unconfirmed_discord_link to confirm it",
                ephemeral=True,
            )
        s.write()
