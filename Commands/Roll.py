import asyncio
from typing import List

import discord
from discord import app_commands

from Golconda.RollInterface import get_lastrolls_for, rollhandle, AuthorError
from Golconda.Storage import evilsingleton
from Golconda.Tools import get_discord_user_char
from gamepack.Dice import Dice


class RollModal(discord.ui.Modal):
    def __init__(self, options, parent):
        super().__init__(
            title="Roll",
        )
        self.parent = parent
        self.roll = discord.ui.TextInput(
            style=discord.TextStyle.short,
            label="Dicecode",
            placeholder=options,
            required=True,
        )

        self.add_item(self.roll)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            # noinspection PyUnresolvedReferences
            await interaction.response.defer()
            await self.parent.add_roll(interaction.user, self.roll.value)
            await interaction.message.edit(embed=self.parent.embed)

        except AuthorError as e:
            await interaction.channel.send(
                interaction.user.mention + "\n".join(e.args), delete_after=20
            )


class RollCall(discord.ui.View):
    prefix = "rollcall:"

    def __init__(self, text: str, options: str, author: discord.User):
        super().__init__(timeout=None)
        self.author = author
        self.text = text
        button = discord.ui.Button(
            label="Do Roll",
            custom_id=self.prefix + "roll",
            row=0,
            style=discord.ButtonStyle.primary,
        )
        button.callback = self.send_modal
        self.add_item(button)
        reveal = discord.ui.Button(
            label="Reveal rolls",
            custom_id=self.prefix + "reveal",
            row=0,
            style=discord.ButtonStyle.success,
        )
        reveal.callback = self.reveal

        selfreveal = discord.ui.Button(
            label="peek",
            custom_id=self.prefix + "selfreveal",
            row=0,
            style=discord.ButtonStyle.success,
        )
        selfreveal.callback = self.self_reveal

        self.add_item(reveal)
        self.add_item(selfreveal)
        self.options = options
        self.revealed = False
        self.rolls = []
        self.original = None
        self.embed = self.rerender()

    async def send_modal(self, interaction: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await interaction.response.send_modal(RollModal(self.options, self))

    async def reveal(self, interaction: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await interaction.response.defer()
        if interaction.user not in [self.author, interaction.client.application.owner]:
            return await interaction.channel.send(
                f"{interaction.user.mention} ... you can't reveal this, because you didn't start it",
                delete_after=5,
            )
        reacting = []
        for i in range(len(self.rolls)):
            revealed, author, result, output, reactions = self.rolls[i]
            if revealed:
                continue
            self.rolls[i][0] = True
            msg = await interaction.channel.send(
                "\n".join(x for x in output if len(x) > 1)
            )
            reacting.extend([msg.add_reaction(r) for r in reactions])

        await interaction.message.edit(embed=self.rerender())
        await asyncio.gather(*reacting)

    async def self_reveal(self, interaction: discord.Interaction):
        for revealed, author, result, output, reactions in reversed(self.rolls):
            if interaction.user == author:
                await interaction.response.send_message(
                    "\n".join(x for x in output if len(x) > 1), ephemeral=True
                )
                break

    def rerender(self):
        rolls = ""
        result: Dice
        for revealed, author, result, output, reactions in self.rolls:
            rolls += f"{author.mention} "
            if revealed:
                rolls += result.name + " " + result.roll_v()
            else:
                rolls += f"{result.name} ==> ..."
            rolls += " " + result.comment + "\n"
        self.embed = discord.Embed(
            description=self.text + "\n" + rolls,
            color=0x05F012,
        )
        return self.embed

    @staticmethod
    def make_send_buffer():
        output = []
        reactions = []

        async def fakereact(content):
            reactions.append(content)

        async def fakesend(content):
            output.append(content)
            return fakesend

        fakesend.add_reaction = fakereact
        fakesend.edit = fakesend
        fakesend.content = ""
        return output, reactions, fakesend

    async def add_roll(self, author: discord.User, roll: str):
        output, reactions, fakesend = self.make_send_buffer()

        result = await rollhandle(
            roll,
            author.mention,
            fakesend,
            nop,
            evilsingleton().storage,
        )
        if not result:
            if not roll.startswith("?"):
                roll = "?" + roll
                await rollhandle(
                    roll,
                    author.mention,
                    fakesend,
                    nop,
                    evilsingleton().storage,
                )
            raise AuthorError(f"{roll} did not produce a result")
        self.rolls.append([False, author, result, output, reactions])
        self.rerender()


# noinspection PyUnusedLocal
async def nop(*args, **kwargs):
    pass


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
                    choices.append(current[: -len(search)] if search else current + a)
        choices = choices[:25]
    return [app_commands.Choice(name=x, value=x) for x in choices]


def register(tree: discord.app_commands.CommandTree):
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

    @app_commands.describe(
        text="Explanatory Text", rolls="comma separated list of recommendations"
    )
    @tree.command(name="callroll", description="call for a roll")
    async def callroll(interaction: discord.Interaction, text: str, rolls: str):
        view = RollCall(text, rolls, interaction.user)
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message(embed=view.embed, view=view)
