import asyncio
import logging
import multiprocessing
from collections import deque
from typing import Callable, Awaitable, Any

import discord
from gamepack.Dice import Dice, DescriptiveError
from gamepack.DiceParser import DiceParser, DiceCodeError, MessageReturn
from gamepack.fasthelpers import avgdev
from gamepack.fengraph import fastdata

from Golconda.Tools import mutate_message

logger = logging.getLogger(__name__)

NUM_EMOJI = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
NUM_EMOJI_2 = ("❗", "‼️", "\U0001f386")
lastrolls: dict[str, list[tuple[str, Dice]]] = {}
lastparse: dict[str, DiceParser] = {}


class AuthorError(Exception):
    pass


def get_lastrolls_for(mention: str) -> list[tuple[str, Dice]]:
    return lastrolls.get(mention, [])


def append_lastroll_for(mention: str, element: tuple[str, Dice]) -> None:
    if mention not in lastrolls:
        lastrolls[mention] = [element]
    else:
        lastrolls[mention].append(element)


async def timeout(func: Callable, arg: Any, time_out: float = 1.0) -> Any:
    """Runs a function in a separate process with a timeout."""
    loop = asyncio.get_running_loop()
    with multiprocessing.Pool(1) as pool:
        return await loop.run_in_executor(
            None, lambda: pool.apply_async(func, (arg,)).get(time_out)
        )


async def prepare(
    msg: str, mention: str, persist: dict
) -> tuple[str, str, DiceParser, bool, str]:
    errreport = msg.startswith("?")
    if errreport:
        msg = msg[1:]

    last_roll_data = get_lastrolls_for(mention)

    lp = lastparse.get(mention, [])
    if msg and all(x == "+" for x in msg):
        roll_number = msg.count("+")
        if roll_number > len(last_roll_data):
            msg = last_roll_data[-1][0] if last_roll_data else ""
        else:
            msg = last_roll_data[-roll_number][0]
    last_roll = [x[1] for x in last_roll_data]  # filter out only the rolls
    roll, dbg = await mutate_message(msg, persist, mention, errreport)

    if "#" in roll:
        comment = roll[roll.find("#") + 1 :]
        roll = roll[: -len(comment) - 1]
    else:
        comment = ""
    roll = roll.strip()
    p = DiceParser(
        persist.setdefault(mention[2:-1], {}).setdefault("defines", {}), last_roll, lp
    )
    lastparse[mention] = p
    return roll, comment, p, errreport, dbg


def construct_multiroll_reply(p: DiceParser) -> str:
    v = Dice.roll_v
    rolls, results = [], []
    for x in p.rolllogs:
        if r := v(x):
            rolls.append(x.name)
            results.append(r)
    if not rolls:
        return ""
    leftlen = max(len(x) for x in rolls)
    res = ""
    for i in range(len(rolls)):
        thislen = leftlen - len(rolls[i])
        res += rolls[i] + ": " + " " * thislen + results[i] + "\n"
    return res


def construct_shortened_multiroll_reply(p: DiceParser, verbose: bool) -> str:
    last = ""
    reply = ""
    v = Dice.roll_v
    for x in p.rolllogs:
        if not x.roll_v():
            continue  # skip empty rolls
        if x.name != last:
            last = x.name
            reply += "\n" + ((x.name + ": ") if verbose else "") + v(x)
        else:
            reply += ", " + str(x.result)
    return reply.strip("\n") + "\n"


async def chunk_reply(
    send: Callable[[str], Awaitable[Any]], premsg: str, message: str
) -> None:
    i = 0
    await send(premsg + "```" + message[i : i + 1990 - len(premsg)] + "```")
    i += 1990 - len(premsg)
    while i < len(message):
        await send("```" + message[i : i + 1990] + "```")
        i += 1990


async def get_reply(
    mention: str,
    comment: str,
    msg: str,
    send: Callable[[str], Awaitable[discord.Message]],
    reply: str,
    r: Dice,
) -> None:
    tosend = mention + f" {comment} `{msg}`:\n{reply} "
    try:
        tosend += r.roll_v() if not reply.endswith(r.roll_v() + "\n") else ""
    except DescriptiveError as e:
        tosend += e.args[0]

    # if message is too long we need a second pass
    if len(tosend) > 2000:
        tosend = (
            f"{mention} {comment} `{msg}`:\n"
            f"{reply[: max(4000 - len(tosend), 0)]} [...]"
            f"{r.roll_v()}"
        )
    # if message is still too long
    if len(tosend) > 2000:
        tosend = (
            f"{mention} {comment} `{msg}`:\n"
            + r.name
            + ": ... try generating less output"
        )
    sent = await send(tosend)
    if r.returnfun.endswith("@"):
        if r.result >= r.max * len(r.returnfun[:-1].split(",")):
            await sent.add_reaction("\U0001f4a5")

        if r.max == 10 and r.amount == 5:
            for frequency in range(1, 11):
                amplitude = r.resonance(frequency)
                if amplitude > 0:
                    await sent.add_reaction(NUM_EMOJI[frequency - 1])
                if amplitude > 1 and len(r.r) == 5:
                    await sent.add_reaction(NUM_EMOJI_2[amplitude - 2])
            if r.resonance(1) > 1:
                await sent.add_reaction("😱")

            if r.result <= minimum_expected(r):
                await sent.edit(
                    content=sent.content
                    + f"\n||minimum expected {minimum_expected(r):.2f}||"
                )
                await sent.add_reaction("🤮")

            if r.result >= maximum_expected(r):
                await sent.edit(
                    content=sent.content
                    + f"\n||maximum expected {maximum_expected(r):.2f}||"
                )
                await sent.add_reaction("🤯")


def minimum_expected(r: Dice) -> float:
    o = fastdata(
        tuple(sorted((int(x) for x in r.returnfun[:-1].split(",")))), r.rerolls
    )
    if not o:
        return float("-inf")
    avg, dev = avgdev(o)
    return avg - dev


def maximum_expected(r: Dice) -> float:
    o = fastdata(
        tuple(sorted((int(x) for x in r.returnfun[:-1].split(",")))), r.rerolls
    )
    if not o:
        return float("inf")
    return sum(avgdev(o))


async def process_roll(
    r: Dice, p: DiceParser, msg: str, comment: str, send: Callable, mention: str
) -> None:
    verbose = p.triggers.get("verbose")
    if isinstance(p.rolllogs, deque) and len(p.rolllogs) > 1:
        reply = construct_multiroll_reply(p)

        if len(reply) > 1950:
            reply = construct_shortened_multiroll_reply(p, bool(verbose))
    else:
        reply = ""
    try:
        if r.name != msg:
            last_roll = get_lastrolls_for(mention)
            msg = f"{msg} ==> {last_roll[-1][0] if last_roll else '?'} ==> {r.name if not reply else ''}"
        await get_reply(mention, comment, msg, send, reply, r)
    except Exception as e:
        logger.exception("Exception during sending", exc_info=e)
        raise
    finally:
        p.lp = None  # discontinue the chain or it would lead to memoryleak


async def rollhandle(
    rollcommand: str,
    mention: str,
    send: Callable[[str], Awaitable[Any]],
    react: Callable[[str], Awaitable[None]],
    persist: dict,
) -> Dice | None:
    if not rollcommand:
        return None
    errreport = True
    r = None
    try:
        original_command = rollcommand
        rollcommand, comment, parser, errreport, dbg = await prepare(
            rollcommand, mention, persist
        )
        if dbg:
            await send(mention + "\n" + dbg)
        if __debug__:
            r = parser.do_roll(rollcommand)
        else:
            r = await timeout(parser.do_roll, rollcommand, 200)
        r.comment = comment
        append_lastroll_for(mention, (rollcommand, r))
        await process_roll(r, parser, original_command, comment, send, mention)
    except DiceCodeError as e:
        lastrolls[mention] = lastrolls.get(mention, [])[:-1]
        if errreport:  # query for error
            raise AuthorError(("Error with roll:\n" + "\n".join(e.args)[:2000]))
    except multiprocessing.TimeoutError:
        await react("\U000023f0")
    except ValueError as e:
        if not any(x in rollcommand for x in "\"'"):
            logger.error(f"not quotes {rollcommand}" + "\n" + "\n".join(e.args))
            raise
        await react("🙃")
    except MessageReturn as e:
        await send(mention + " " + str(e.args[0]))
    except Exception as e:
        ermsg = f"big oof during rolling {rollcommand}" + "\n" + "\n".join(e.args)
        logger.exception(ermsg, exc_info=e)
        if errreport:  # query for error
            raise AuthorError(ermsg[:2000])
        else:
            await react("😕")
        raise
    return r


def print_(name: str) -> Callable[[str], Awaitable[None]]:
    async def wrapped_print(*args: Any, **kwargs: Any) -> None:
        print(name, end=": ")
        print(*args, **kwargs)

    return wrapped_print


# mock a discord.User int _author
_author = type("User", (object,), {"mention": "test_mention"})()
_send = print_("send")
_react = print_("react")
_persist: dict[str, Any] = dict()
