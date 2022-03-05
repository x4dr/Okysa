from typing import AsyncGenerator

import hikari

from Golconda.Slashing import Slash


def extract_mode(msg):
    mode = None
    if msg[-1].strip() in ("under", "asc", "below"):
        mode = 1
        msg = msg[:-1]
    if msg[-1].strip() in ("over", "desc", "above"):
        mode = -1
        msg = msg[:-1]
    return msg, mode


@Slash.cmd("oracle", "Statistical Analysis and Predicted-Value")
def common(cmd: Slash):
    print("called")


@Slash.option(
    "advantage",
    "negative values mean disadvantage",
    hikari.OptionType.INTEGER,
    required=False,
)
@Slash.option(
    "additional",
    "all the rest, separated by spaces",
    required=False,
)
async def versus():
    if len(params + [mod]) == len(msg[1:]) == 3:
        it = versus(params, msg[1:], ctx.mode)
    else:
        await ctx.send(
            ctx.author.mention + "versus mode needs exactly 3 numbers on each side"
        )
        return
    feedback = (
        ",".join(str(x) for x in params)
        + f"@5R{mod} v "
        + ",".join(str(x) for x in msg[1:-1])
        + f"@5R{msg[-1]}"
    )


@Slash.option("first", "first of the selectors", hikari.OptionType.INTEGER)
@Slash.sub("selectors", "get odds for the selector system", common)
async def oraclehandle(cmd: Slash):
    mod = cmd.get("advantage", 0)
    additional = cmd.get("additional selectors", "").split(" ")
    try:
        additional = [int(x) for x in additional]
    except ValueError:
        await cmd.respond_instant_ephemeral(
            "Error: The given additional selectors didnt make sense."
        )
        return
    params = [cmd.get("first")] + additional

    async def work()-> AsyncGenerator[dict[str,str]]:
        it = chances(params, mod, mode=ctx.mode)
        feedback = (
            ",".join(str(x) for x in params) + "@5" + (("R" + str(mod)) if mod else "")
        )
        i = None
        for i in it:
            if isinstance(i, str):
                yield {"content": cmd.user.mention + " " + i}
        else:
            n, avg, dev = i
            yield {
                "content": f"{cmd.user.mention} ```{feedback} avg: {avg} dev: {dev}\n{n}```"
            }

    await cmd.respond_later(work())


@oraclehandle.command("try")
async def oracle_try(self, ctx, *msg):
    msg = self.common(ctx, msg)
    ctx.sentmessage = await ctx.send("Applying the numerical HAMMER for 10 seconds...")
    r = await timeout(montecarlo, " ".join(msg), 12)
    await ctx.sentmessage.edit(
        content=ctx.author.mention + ctx.comment + "\n" + str(r)[:1950]
    )


@oraclehandle.command("show")
async def oracle_show(
    self,
    ctx,
    params: Greedy[int],
    comment: Optional[str],
):
    mod = params[-2]
    percentiles = params[-1]
    params = params[:-2]
    await self.common(ctx, comment)
    it = chances(params, mod, percentiles, mode=ctx.mode)
    sentmessage = await ctx.send(ctx.author.mention + ctx.comment + " " + next(it))
    for n in it:
        if isinstance(n, str):
            await sentmessage.edit(content=ctx.author.mention + ctx.comment + " " + n)
        else:
            await sentmessage.delete(delay=0.1)
            await ctx.send(
                ctx.author.mention + ctx.comment,
                file=discord.File(n, "graph.png"),
            )
