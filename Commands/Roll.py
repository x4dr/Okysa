import asyncio
from typing import List, Any, Callable, Optional

import discord
from discord import app_commands
from gamepack.Dice import Dice

from Golconda.CharacterService import get_discord_user_char
from Golconda.RollInterface import get_lastrolls_for, rollhandle, AuthorError
from Golconda.Storage import evilsingleton


class RollCommand:
    """Roll dice using various notations.

    Commands:
    - r <dicecode>: Roll dice (e.g., r 1d20+5).
    - callroll <text> <rolls>: Start a group roll call.

    Tip: Use ?roll <command> for parameter details.
    """

    @staticmethod
    async def handle(ctx, args: list[str]) -> None:
        if len(args) < 2:
            return

        subcommand = args[1].lower()
        if subcommand == "callroll":
            await ctx.reply(
                "CallRoll is currently only supported via slash commands on Discord."
            )
            return

        # Treat as roll code (starting from index 1)
        rollcode = " ".join(args[1:])
        try:
            await RollCommand.roll_logic(
                rollcode, ctx.author.mention, ctx.reply, ctx.message.add_reaction
            )
        except Exception as e:
            await ctx.reply(f"Roll error: {e}")

    @staticmethod
    async def roll_logic(
        rollcode: str, user_mention: str, send_fn: Callable, react_fn: Callable
    ) -> Optional[Dice]:
        """Roll dice using standard or special notations.
        Usage: r <dicecode>
        - <dicecode>: Standard (e.g., 1d20+5, 3d6) or selector (e.g., 3 4 5@2) notation.
        """
        s = evilsingleton()
        s = evilsingleton()
        return await rollhandle(
            rollcode,
            user_mention,
            send_fn,
            react_fn,
            s.storage,
        )


class RollModal(discord.ui.Modal):
    def __init__(self, options: str, parent: "RollCall") -> None:
        super().__init__(title="Roll")
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
            await interaction.response.defer()
            await self.parent.add_roll(interaction.user, self.roll.value)
            if interaction.message:
                await interaction.message.edit(embed=self.parent.embed)
        except AuthorError as e:
            if interaction.channel and hasattr(interaction.channel, "send"):
                await interaction.channel.send(
                    interaction.user.mention + "\n".join(e.args), delete_after=20
                )


class RollCall(discord.ui.View):
    prefix = "rollcall:"

    def __init__(
        self, text: str, options: str, author: discord.User | discord.Member
    ) -> None:
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
        self.rolls: list[list[Any]] = []
        self.original = None
        self.embed = self.rerender()

    async def send_modal(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(RollModal(self.options, self))

    async def reveal(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if interaction.user != self.author:
            if not (
                interaction.client.application
                and interaction.client.application.owner == interaction.user
            ):
                if interaction.channel and hasattr(interaction.channel, "send"):
                    await interaction.channel.send(
                        f"{interaction.user.mention} ... you can't reveal this, because you didn't start it",
                        delete_after=5,
                    )
                return
        reacting = []
        for i in range(len(self.rolls)):
            revealed, author, result, output, reactions = self.rolls[i]
            if revealed:
                continue
            self.rolls[i][0] = True
            if interaction.channel and hasattr(interaction.channel, "send"):
                msg = await interaction.channel.send(
                    "\n".join(x for x in output if len(x) > 1)
                )
                reacting.extend([msg.add_reaction(r) for r in reactions])
        if interaction.message:
            await interaction.message.edit(embed=self.rerender())
        await asyncio.gather(*reacting)

    async def self_reveal(self, interaction: discord.Interaction) -> None:
        for revealed, author, result, output, reactions in reversed(self.rolls):
            if interaction.user == author:
                await interaction.response.send_message(
                    "\n".join(x for x in output if len(x) > 1), ephemeral=True
                )
                break

    def rerender(self) -> discord.Embed:
        rolls = ""
        for revealed, author, result, output, reactions in self.rolls:
            rolls += f"{author.mention} "
            rolls += (
                (result.name + " " + result.roll_v())
                if revealed
                else f"{result.name} ==> ..."
            )
            rolls += " " + result.comment + "\n"
        self.embed = discord.Embed(description=self.text + "\n" + rolls, color=0x05F012)
        return self.embed

    @staticmethod
    def make_send_buffer() -> tuple[list[str], list[str], Callable]:
        output, reactions = [], []

        async def fakereact(content: str) -> None:
            reactions.append(content)

        async def fakesend(content: str) -> "Callable":
            output.append(content)
            return fakesend

        setattr(fakesend, "add_reaction", fakereact)
        setattr(fakesend, "edit", fakesend)
        setattr(fakesend, "content", "")
        return output, reactions, fakesend

    async def add_roll(self, author: discord.User | discord.Member, roll: str) -> None:
        output, reactions, fakesend = self.make_send_buffer()
        result = await RollCommand.roll_logic(
            roll, author.mention, fakesend, getattr(fakesend, "add_reaction")
        )
        if not result:
            if not roll.startswith("?"):
                roll = "?" + roll
                await RollCommand.roll_logic(
                    roll, author.mention, fakesend, getattr(fakesend, "add_reaction")
                )
            raise AuthorError(f"{roll} did not produce a result")
        self.rolls.append([False, author, result, output, reactions])
        self.rerender()


async def roll_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice]:
    if not current:
        lastroll = get_lastrolls_for(interaction.user.mention)
        return [app_commands.Choice(name=x[0], value=x[0]) for x in lastroll]
    try:
        char = get_discord_user_char(interaction.user)
    except KeyError:
        return []
    choices = []
    if "," not in current:
        for c_name, c in char.Categories.items():
            att_key = list(char.headings_used["categories"][c_name].keys())[0]
            for a in char.Categories[c_name][att_key].keys():
                if current.strip().lower() in a.lower():
                    choices.append(a)
    else:
        for c_name, c in char.Categories.items():
            skill_key = list(char.headings_used["categories"][c_name].keys())[1]
            for a in char.Categories[c_name][skill_key].keys():
                search = current.replace(",", " ").split(" ")[-1]
                if search.strip().lower() in a.lower():
                    choices.append(current[: -len(search)] if search else current + a)
    return [app_commands.Choice(name=x, value=x) for x in choices[:25]]


def register(tree: discord.app_commands.CommandTree) -> None:
    @app_commands.describe(roll="the input for the diceroller")
    @tree.command(name="r", description="invoke the diceroller")
    @app_commands.autocomplete(roll=roll_autocomplete)
    async def doroll(interaction: discord.Interaction, roll: str) -> None:
        mention = interaction.user.mention
        try:
            await interaction.response.send_message("rolled: " + roll + "\n")
            content: list[str] = []

            async def send(x: str) -> discord.Message:
                content.append(x)
                return await interaction.edit_original_response(
                    content="\n".join(content)
                )

            orig = await interaction.original_response()
            await RollCommand.roll_logic(roll, mention, send, orig.add_reaction)
        except AuthorError as e:
            await interaction.user.send(e.args[0])

    @app_commands.describe(
        text="Explanatory Text", rolls="comma separated list of recommendations"
    )
    @tree.command(name="callroll", description="call for a roll")
    async def callroll(interaction: discord.Interaction, text: str, rolls: str) -> None:
        view = RollCall(text, rolls, interaction.user)
        await interaction.response.send_message(embed=view.embed, view=view)
