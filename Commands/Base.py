import re
from typing import Generator, List

import discord
from discord import app_commands

from Golconda import Rights
from Golconda.RollInterface import rollhandle, AuthorError, get_lastrolls_for
from Golconda.Storage import evilsingleton
from Golconda.Tools import get_discord_user_char

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
        msg = msg.strip("` ")
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

    @tree.command(name="list", description="lists the last rolls and results")
    async def rolllist(interaction: discord.Interaction):
        roll_list = get_lastrolls_for(interaction.user.mention)
        msg = ""
        n = 0
        for roll in roll_list:
            msg += f"{len(roll_list)-n}: {roll[0]} -> {roll[1].r}\n"
            n += 1
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message(msg, ephemeral=True)

    async def roll_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice]:
        if not current:
            lastroll = get_lastrolls_for(interaction.user.mention)
            choices = [app_commands.Choice(name=x[0], value=x[0]) for x in lastroll]
            return choices

        try:
            char = get_discord_user_char(interaction.user)
        except KeyError:
            return []
        choices = []
        if "," not in current:
            # get attributes first
            for c_name, c in char.Categories.items():
                att_key = list(char.headings_used["categories"][c_name].keys())[0]
                for a in char.Categories[c_name][att_key].keys():
                    if current.strip().lower() in a.lower():
                        choices.append(a)
        else:
            # extend with skills
            for c_name, c in char.Categories.items():
                skill_key = list(char.headings_used["categories"][c_name].keys())[1]
                for a in char.Categories[c_name][skill_key].keys():
                    search = current.replace(",", " ").split(" ")[-1]
                    if search.strip().lower() in a.lower():
                        choices.append(
                            current[: -len(search)] if search else current + a
                        )
            choices = choices[:25]
        return [app_commands.Choice(name=x, value=x) for x in choices]

    @app_commands.describe(roll="the input for the diceroller")
    @tree.command(name="r", description="invoke the diceroller")
    @app_commands.autocomplete(roll=roll_autocomplete)
    async def doroll(interaction: discord.Interaction, roll: str):
        s = evilsingleton()
        mention = interaction.user.mention
        try:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("rolled: " + roll + "\n")

            content = []

            async def send(x):
                content.append(x)
                return await interaction.edit_original_response(
                    content="\n".join(content)
                )

            await rollhandle(
                roll,
                mention,
                send,
                (await interaction.original_response()).add_reaction,
                s.storage,
            )
        except AuthorError as e:
            await interaction.user.send(e.args[0])
        # noinspection PyUnresolvedReferences

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
