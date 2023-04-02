from typing import AsyncGenerator, Optional

import discord
from discord import app_commands
from gamepack.fengraph import chances, montecarlo, versus

from Golconda.RollInterface import timeout
from Golconda.Tools import respond_later

modechoices = [
    app_commands.Choice(name="under", value=1),
    app_commands.Choice(name="over", value=-1),
]


def register(tree: discord.app_commands.CommandTree):
    group = app_commands.Group(
        name="oracle", description="Statistical Analysis and Predicted-Values"
    )

    async def process_work(feedback, it, interaction: discord.Interaction):
        i = None
        for i in it:
            if isinstance(i, str):
                yield {"content": interaction.user.mention + " " + i}
        else:
            n, avg, dev = i
            yield {
                "content": f"{interaction.user.mention} ```{feedback} avg: {avg} dev: {dev}\n{n}```"
            }

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
            sel1 = [int(x) for x in selector1.strip().split(" ")]
            sel2 = [int(x) for x in selector2.strip().split(" ")]
            assert sel1[0]
            assert sel2[0]
        except (ValueError, AssertionError):
            await r.send_message(
                "error: The given selectors didnt make sense.", ephemeral=True
            )
            return

        async def work() -> AsyncGenerator[dict[str, str], None]:
            it = versus(sel1 + [mod1], sel2 + [mod2], int(mode))
            feedback = (
                ",".join(str(x) for x in sel1)
                + f"@5R{mod1} v "
                + ",".join(str(x) for x in sel2)
                + f"@5R{mod2}"
            )
            async for x in process_work(feedback, it, interaction):
                yield x

        await respond_later(interaction, work())

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
            selector = [int(x) for x in selectors.strip().split(" ") if x]
        except ValueError:
            await r.send_message(
                "Error: The given additional selectors didnt make sense.",
                ephemeral=True,
            )
            return

        async def work() -> AsyncGenerator[dict[str, str], None]:
            it = chances(selector, advantage, mode=int(mode and mode.value))
            feedback = (
                ",".join(str(x) for x in selector)
                + "@5"
                + (("R" + str(advantage)) if advantage else "")
            )
            async for x in process_work(feedback, it, interaction):
                yield x

        await respond_later(interaction, work())

    @group.command(name="try", description="experimental")
    @app_commands.describe(roll="what to throw at the wall")
    async def oracle_try(interaction: discord.Interaction, roll: str):
        # noinspection PyTypeChecker
        r: discord.InteractionResponse = interaction.response
        await r.send_message("Applying the numerical HAMMER for 10 seconds...")
        r = await timeout(montecarlo, " ".join(roll), 10)
        await r.edit_message(content=interaction.user.mention + "\n" + str(r)[:1950])

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
            selector = [int(x) for x in selectors.strip().split(" ") if x]
        except ValueError:
            await r.send_message(
                "Error: The given additional selectors didnt make sense.",
                ephemeral=True,
            )
            return
        it = chances(selector, advantage, percentiles, mode=int(mode and mode.value))

        async def work() -> AsyncGenerator[dict, None]:
            for n in it:
                if isinstance(n, str):
                    yield {"content": n}
                else:
                    yield {
                        "file": discord.File(n, "graph.png"),
                    }

        await respond_later(interaction, work())

    tree.add_command(group)
