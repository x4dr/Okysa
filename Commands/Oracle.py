from typing import Optional

import discord
from discord import app_commands

from Golconda.RollInterface import timeout
from gamepack.Dice import DescriptiveError
from gamepack.fengraph import chances, versus
from gamepack.fasthelpers import montecarlo

modechoices = [
    app_commands.Choice(name="under", value=1),
    app_commands.Choice(name="over", value=-1),
]


def register(tree: discord.app_commands.CommandTree):
    group = app_commands.Group(
        name="oracle", description="Statistical Analysis and Predicted-Values"
    )

    # noinspection PyTypeChecker
    @group.command(name="versus", description="odds of one selector roll vs the other")
    @app_commands.describe(
        selector1="space separated",
        selector2="space separated",
        advantage1="negative means disadvantage",
        advantage2="negative means disadvantage",
        mode="display mode",
    )
    async def v(
        interaction: discord.Interaction,
        selector1: Optional[str] = "",
        selector2: Optional[str] = "",
        advantage1: Optional[int] = 0,
        advantage2: Optional[int] = 0,
        mode: Optional[int] = 0,
    ):
        r: discord.InteractionResponse = interaction.response
        mod1 = advantage1
        mod2 = advantage2
        try:
            sel1 = tuple(int(x) for x in selector1.strip().split(" "))
            sel2 = tuple(int(x) for x in selector2.strip().split(" "))
            assert sel1[0]
            assert sel2[0]
        except (ValueError, AssertionError):
            await r.send_message(
                "error: The given selectors didnt make sense.", ephemeral=True
            )
            return
        try:
            work, avg, dev = versus(sel1, sel2, mod1, mod2, int(mode))
            feedback = (
                ",".join(str(x) for x in sel1)
                + f"@5R{mod1} v "
                + ",".join(str(x) for x in sel2)
                + f"@5R{mod2}"
            )

            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                f"{interaction.user.mention} ```{feedback} avg: {avg} dev: {dev}\n{work}```"
            )
        except DescriptiveError as e:
            await r.send_message(f"Error: {e}", ephemeral=True)

    @group.command(name="selectors", description="get odds for the selector system")
    @app_commands.describe(
        selectors="selectors separated by spaces",
        advantage="negative means disadvantage",
        mode="display mode",
    )
    @app_commands.choices(mode=modechoices)
    async def selectors_ascii(
        interaction: discord.Interaction,
        selectors: str,
        advantage: Optional[int] = 0,
        mode: app_commands.Choice[int] = 0,
    ):
        # noinspection PyTypeChecker
        r: discord.InteractionResponse = interaction.response
        try:
            selector = tuple(int(x) for x in selectors.strip().split(" ") if x)
        except ValueError:
            await r.send_message(
                "Error: The given additional selectors didnt make sense.",
                ephemeral=True,
            )
            return
        try:
            graph, avg, dev = chances(
                selector, advantage, mode=int(mode and mode.value)
            )
            feedback = (
                ",".join(str(x) for x in selector)
                + "@5"
                + (("R" + str(advantage)) if advantage else "")
            )

            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                f"{interaction.user.mention} ```{feedback} avg: {avg} dev: {dev} \n{graph}```"
            )

        except DescriptiveError as e:
            await r.send_message(f"Error: {e}", ephemeral=True)

    @group.command(name="try", description="experimental")
    @app_commands.describe(roll="what to throw at the wall")
    async def oracle_try(interaction: discord.Interaction, roll: str):
        # noinspection PyTypeChecker
        r: discord.InteractionResponse = interaction.response
        await r.send_message("Applying the numerical HAMMER for 10 seconds...")
        r = await timeout(
            montecarlo, " ".join(roll), 12
        )  # internal timeout is 10, so 2 seconds of overhead
        await interaction.edit_original_response(
            content=interaction.user.mention
            + "\n```"
            + str(r)[: 2000 - len(interaction.user.mention) - 10]
            + "```"
        )

    @group.command(name="showselectors", description="like oracle, but with graphics")
    @app_commands.describe(
        selectors="selectors separated by spaces",
        advantage="negative means disadvantage",
        percentiles="how many percentiles to draw",
        mode="display mode",
    )
    async def oracle_show(
        interaction: discord.Interaction,
        selectors: str,
        advantage: Optional[int] = 0,
        percentiles: int = 0,
        mode: app_commands.Choice[int] = 0,
    ):
        # noinspection PyTypeChecker
        r: discord.InteractionResponse = interaction.response
        try:
            selector = tuple(int(x) for x in selectors.strip().split(" ") if x)
        except ValueError:
            await r.send_message(
                "Error: The given additional selectors didnt make sense.",
                ephemeral=True,
            )
            return
        try:
            w = chances(selector, advantage, percentiles, mode=int(mode and mode.value))
        except DescriptiveError as e:
            await r.send_message(f"Error: {e}", ephemeral=True)
            return

        # noinspection PyUnresolvedReferences
        await interaction.response.send_message(file=discord.File(w, "graph.png"))

    tree.add_command(group)
