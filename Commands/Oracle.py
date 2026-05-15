import discord
from discord import app_commands
from typing import Optional
from gamepack.Dice import DescriptiveError
from gamepack.fasthelpers import montecarlo
from gamepack.fengraph import chances, versus
from Golconda.RollInterface import timeout


class OracleCommand:
    """Statistical analysis and predicted-values.

    Commands:
    - versus <sel1> <sel2> [adv1] [adv2] [mode]: Odds of one selector roll vs another.
    - selectors <selectors> [adv] [mode]: Get odds for the selector system.
    - try <roll>: Run numerical simulation for 10 seconds.
    - show <selectors> [adv] [percentiles] [mode]: Generate a graph of probabilities.

    Tip: Use ?oracle <command> for parameter details.
    Example: oracle versus 3 4 5  3 4 6
    """

    @staticmethod
    def parse_selectors(selectors_str: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in selectors_str.strip().split(" ") if x)
        except ValueError, AttributeError:
            raise DescriptiveError("The given selectors didn't make sense.")

    @staticmethod
    async def versus_logic(
        sel1_str: str, sel2_str: str, mod1: int = 0, mod2: int = 0, mode: int = 0
    ) -> str:
        """Compare the odds of two different selector rolls.
        Usage: oracle versus <sel1> <sel2> [adv1] [adv2] [mode]
        - <sel1>, <sel2>: Space-separated integers (e.g., 3 4 5). Face values of the dice in your pool.
        - [adv1], [adv2]: Optional. Extra dice to roll (positive for advantage, negative for disadvantage).
        - [mode]: Optional. 1 for 'under', -1 for 'over'.
        """
        sel1 = OracleCommand.parse_selectors(sel1_str)
        sel2 = OracleCommand.parse_selectors(sel2_str)
        work, avg, dev = versus(sel1, sel2, mod1, mod2, mode)
        feedback = (
            ",".join(str(x) for x in sel1)
            + f"@5R{mod1} v "
            + ",".join(str(x) for x in sel2)
            + f"@5R{mod2}"
        )
        return f"{feedback} avg: {avg} dev: {dev}\n{work}"

    @staticmethod
    async def selectors_logic(
        selectors_str: str, advantage: int = 0, mode: int = 0
    ) -> str:
        """Get odds for the selector dice system.
        Usage: oracle selectors <selectors> [adv] [mode]
        - <selectors>: Space-separated integers (e.g., 3 4 5).
        - [adv]: Optional. Positive for advantage, negative for disadvantage.
        - [mode]: Optional. 1 for 'under', -1 for 'over'.
        """
        selector = OracleCommand.parse_selectors(selectors_str)
        graph, avg, dev = chances(selector, advantage, mode=mode)
        feedback = (
            ",".join(str(x) for x in selector)
            + "@5"
            + (("R" + str(advantage)) if advantage else "")
        )
        return f"{feedback} avg: {avg} dev: {dev} \n{graph}"

    @staticmethod
    async def try_logic(roll: str) -> str:
        """Run a numerical simulation (Monte Carlo) to estimate odds for complex rolls.
        Usage: oracle try <roll>
        - <roll>: Any dice code (e.g., 3d6 + 2d4 > 10).
        """
        return await timeout(montecarlo, roll, 12)

    @staticmethod
    async def show_logic(
        selectors_str: str, advantage: int = 0, percentiles: int = 0, mode: int = 0
    ) -> str:
        """Generate a probability distribution graph.
        Usage: oracle show <selectors> [adv] [percentiles] [mode]
        - <selectors>: Space-separated integers.
        - [adv]: Advantage/Disadvantage.
        - [percentiles]: How many percentile markers to draw.
        - [mode]: 1 for under, -1 for over.
        """
        selector = OracleCommand.parse_selectors(selectors_str)
        return chances(selector, advantage, percentiles, mode=mode)

    @staticmethod
    async def handle(ctx, args: list[str]) -> None:
        if len(args) < 2:
            return

        subcommand = args[1].lower()
        try:
            match subcommand:
                case "versus":
                    res = await OracleCommand.versus_logic(*args[2:])
                    await ctx.reply(f"```{res}```")
                case "selectors":
                    res = await OracleCommand.selectors_logic(*args[2:])
                    await ctx.reply(f"```{res}```")
                case "try":
                    roll = " ".join(args[2:])
                    res = await OracleCommand.try_logic(roll)
                    await ctx.reply(f"```{res}```")
                case "show":
                    res = await OracleCommand.show_logic(*args[2:])
                    await ctx.reply(f"Resulting graph path: {res}")
        except DescriptiveError as e:
            await ctx.reply(f"Error: {e}")
        except Exception as e:
            await ctx.reply(f"An unexpected error occurred: {e}")


modechoices = [
    app_commands.Choice(name="under", value=1),
    app_commands.Choice(name="over", value=-1),
]


def register(tree: discord.app_commands.CommandTree) -> None:
    group = app_commands.Group(
        name="oracle", description="Statistical Analysis and Predicted-Values"
    )

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
        selector1: str = "",
        selector2: str = "",
        advantage1: int = 0,
        advantage2: int = 0,
        mode: int = 0,
    ) -> None:
        try:
            res = await OracleCommand.versus_logic(
                selector1, selector2, advantage1, advantage2, mode
            )
            await interaction.response.send_message(
                f"{interaction.user.mention} ```{res}```"
            )
        except DescriptiveError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

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
        advantage: int = 0,
        mode: Optional[app_commands.Choice[int]] = None,
    ) -> None:
        try:
            res = await OracleCommand.selectors_logic(
                selectors, advantage, mode.value if mode else 0
            )
            await interaction.response.send_message(
                f"{interaction.user.mention} ```{res}```"
            )
        except DescriptiveError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @group.command(name="try", description="experimental")
    @app_commands.describe(roll="what to throw at the wall")
    async def oracle_try(interaction: discord.Interaction, roll: str) -> None:
        await interaction.response.send_message(
            "Applying the numerical HAMMER for 10 seconds..."
        )
        res = await OracleCommand.try_logic(roll)
        await interaction.edit_original_response(
            content=interaction.user.mention + "\n```" + str(res)[:1900] + "```"
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
        advantage: int = 0,
        percentiles: int = 0,
        mode: Optional[app_commands.Choice[int]] = None,
    ) -> None:
        try:
            path = await OracleCommand.show_logic(
                selectors, advantage, percentiles, mode.value if mode else 0
            )
            await interaction.response.send_message(
                file=discord.File(path, "graph.png")
            )
        except DescriptiveError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    tree.add_command(group)
