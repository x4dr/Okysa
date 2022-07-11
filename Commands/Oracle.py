from typing import AsyncGenerator, Type

import hikari

from gamepack.fengraph import chances, montecarlo, versus

from Golconda.RollInterface import timeout
from Golconda.Slash import Slash

modechoices = [
    hikari.CommandChoice(name="under", value="1"),
    hikari.CommandChoice(name="over", value="-1"),
]

INT = hikari.OptionType.INTEGER


def register(slash: Type[Slash]):
    # noinspection PyUnusedLocal
    @Slash.cmd("oracle", "Statistical Analysis and Predicted-Value")
    async def oracle_common(cmd: Slash):
        ...

    async def getparams(cmd: Slash):
        mod = cmd.get("advantage", 0)
        params = cmd.get("selectors", "").split(" ")
        try:
            params = [int(x) for x in params if x]
        except ValueError:
            await cmd.respond_instant_ephemeral(
                "Error: The given additional selectors didnt make sense."
            )
            return
        params = params
        return params, mod

    async def process_work(feedback, it, cmd):
        i = None
        for i in it:
            if isinstance(i, str):
                yield {"content": cmd.author.mention + " " + i}
        else:
            n, avg, dev = i
            yield {
                "content": f"{cmd.author.mention} ```{feedback} avg: {avg} dev: {dev}\n{n}```"
            }

    @Slash.option("mode", "display mode", choices=modechoices, required=False)
    @Slash.option("advantage2", "negative means disadvantage", INT)
    @Slash.option("selectors2", "space separated")
    @Slash.option("advantage1", "negative means disadvantage", INT)
    @Slash.option("selectors1", "space separated")
    @Slash.sub("versus", "odds of one selector roll vs the other", of="oracle")
    async def v(cmd: Slash):
        mod1 = cmd.get("advantage1", 0)
        mod2 = cmd.get("advantage2", 0)
        try:
            sel1 = [int(x) for x in cmd.get("selectors1", "").split(" ")]
            sel2 = [int(x) for x in cmd.get("selectors2", "").split(" ")]
            assert sel1[0]
            assert sel2[0]
        except (ValueError, AssertionError):
            await cmd.respond_instant_ephemeral(
                "Error: The given selectors didnt make sense."
            )
            return

        async def work() -> AsyncGenerator[dict[str, str], None]:
            it = versus(sel1 + [mod1], sel2 + [mod2], int(cmd.get("mode", 0)))
            feedback = (
                ",".join(str(x) for x in sel1)
                + f"@5R{mod1} v "
                + ",".join(str(x) for x in sel2)
                + f"@5R{mod2}"
            )
            async for x in process_work(feedback, it, cmd):
                yield x

        await cmd.respond_later(work())

    @Slash.option("mode", "display mode", choices=modechoices, required=False)
    @Slash.option(
        "advantage",
        "negative values mean disadvantage",
        INT,
        required=False,
    )
    @Slash.option("selectors", "selectors separated by spaces")
    @Slash.sub("selectors", "get odds for the selector system", "oracle")
    async def oraclehandle(cmd: Slash):
        params, mod = await getparams(cmd)
        print("called oraclehandle with ", params, mod)

        async def work() -> AsyncGenerator[dict[str, str], None]:
            it = chances(params, mod, mode=int(cmd.get("mode", 0)))
            feedback = (
                ",".join(str(x) for x in params)
                + "@5"
                + (("R" + str(mod)) if mod else "")
            )
            async for x in process_work(feedback, it, cmd):
                yield x

        await cmd.respond_later(work())

    @slash.option("roll", "what to throw at the wall")
    @slash.sub("try", "experimental", of="oracle")
    async def oracle_try(cmd: Slash):
        msg = cmd.get("roll")
        await cmd.respond_instant("Applying the numerical HAMMER for 10 seconds...")
        r = await timeout(montecarlo, " ".join(msg), 12)
        await cmd.change_response(content=cmd.author.mention + "\n" + str(r)[:1950])

    @Slash.option("mode", "display mode", choices=modechoices, required=False)
    @Slash.option("percentiles", "how many percentiles to draw", INT, required=False)
    @Slash.option("selectors", "selectors separated by spaces")
    @slash.sub("showselectors", "like oracle, but with graphics", of="oracle")
    async def oracle_show(cmd: Slash):
        params, mod = await getparams(cmd)
        it = chances(params, mod, cmd.get("percentiles", 0), int(cmd.get("mode", 0)))

        async def work() -> AsyncGenerator[dict, None]:
            for n in it:
                if isinstance(n, str):
                    yield {"user_mentions": [cmd.author.mention], "content": n}
                else:
                    yield {
                        "user_mentions": [cmd.author.mention],
                        "file": hikari.Bytes(n, "graph.png"),
                    }

        await cmd.respond_later(work())
