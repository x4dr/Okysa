import ctypes
import logging
import multiprocessing
import threading
from collections import deque
from typing import Callable, Awaitable

import discord
from gamepack.Dice import Dice, DescriptiveError
from gamepack.DiceParser import DiceParser, DiceCodeError, MessageReturn
from gamepack.fengraph import fastdata
from gamepack.fasthelpers import avgdev

from Golconda.Tools import mutate_message

logger = logging.getLogger(__name__)

numemoji = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
numemoji_2 = ("❗", "‼️", "\U0001F386")
lastrolls = {}
lastparse = {}


class AuthorError(Exception):
    pass


def get_lastrolls_for(mention: str) -> [(str, Dice)]:
    return lastrolls.get(mention, [])


def append_lastroll_for(mention: str, element: (str, Dice)):
    if mention not in lastrolls:
        lastrolls[mention] = [element]
    else:
        lastrolls[mention].append(element)


def terminate_thread(thread: threading.Thread):
    """Terminates a python thread from another thread
    :param thread: a threading.Thread instance
    """
    if not thread.is_alive():
        return

    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident), exc)
    if res == 0:
        raise ValueError("nonexistent thread id")
    if res > 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


async def prepare(
    msg: str, mention: str, persist: dict
) -> (str, str, DiceParser, bool):
    errreport = msg.startswith("?")
    if errreport:
        msg = msg[1:]

    last_roll = get_lastrolls_for(mention)

    lp = lastparse.get(mention, [])
    if msg and all(x == "+" for x in msg):
        roll_number = msg.count("+")
        if roll_number > len(last_roll):
            msg = last_roll[-1] if last_roll else ""
        else:
            msg = last_roll[-roll_number]
        msg = msg[0]
    last_roll = [x[1] for x in last_roll]  # filter out only the rolls
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


def construct_multiroll_reply(p: DiceParser):
    v = Dice.roll_v
    rolls, results = [], []
    for x in p.rolllogs:
        if r := v(x):
            rolls.append(x.name)
            results.append(r)
    leftlen = max(len(x) for x in rolls)
    res = ""
    for i in range(len(rolls)):
        thislen = leftlen - len(rolls[i])
        res += rolls[i] + ": " + " " * thislen + results[i] + "\n"
    return res


def construct_shortened_multiroll_reply(p: DiceParser, verbose):
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


async def chunk_reply(send, premsg, message):
    i = 0
    await send(premsg + "```" + message[i : i + 1990 - len(premsg)] + "```")
    i += 1990 - len(premsg)
    while i < len(message):
        await send("```" + message[i : i + 1990] + "```")
        i += 1990


async def get_reply(
    mention,
    comment,
    msg,
    send: Callable[[str], Awaitable[discord.Message]],
    reply,
    r: Dice,
):
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
                    await sent.add_reaction(numemoji[frequency - 1])
                if amplitude > 1 and len(r.r) == 5:
                    await sent.add_reaction(numemoji_2[amplitude - 2])
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


async def process_roll(r: Dice, p: DiceParser, msg: str, comment, send, mention):
    verbose = p.triggers.get("verbose", None)
    if isinstance(p.rolllogs, deque) and len(p.rolllogs) > 1:
        reply = construct_multiroll_reply(p)

        if len(reply) > 1950:
            reply = construct_shortened_multiroll_reply(p, verbose)
    else:
        reply = ""
    try:
        if r.name != msg:
            last_roll = get_lastrolls_for(mention)
            msg = f"{msg} ==> {last_roll[-1][0] if last_roll else '?'} ==> {r.name if not reply else ''}"
        await get_reply(mention, comment, msg, send, reply, r)
    except Exception as e:
        logger.exception("Exception during sending", e)
        raise
    finally:
        p.lp = None  # discontinue the chain or it would lead to memoryleak


async def timeout(func, arg, time_out=1):
    with multiprocessing.Pool(1) as pool:
        task = pool.apply_async(func, (arg,))
        return task.get(time_out)


async def rollhandle(
    rollcommand: str,
    mention: str,
    send: discord.Message.reply,
    react: discord.Message.add_reaction,
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
        await react("\U000023F0")
    except ValueError as e:
        if not any(x in rollcommand for x in "\"'"):
            logger.error(f"not quotes {rollcommand}" + "\n" + "\n".join(e.args))
            raise
        await react("🙃")
    except MessageReturn as e:
        await send(mention + " " + str(e.args[0]))
    except Exception as e:
        ermsg = f"big oof during rolling {rollcommand}" + "\n" + "\n".join(e.args)
        logger.exception(ermsg, e)
        if errreport:  # query for error
            raise AuthorError(ermsg[:2000])
        else:
            await react("😕")
        raise
    return r


# an async wrapper around print
def print_(name: str) -> Callable[[str], Awaitable[None]]:
    async def wrapped_print(*args, **kwargs):
        print(name, end=": ")
        print(*args, **kwargs)

    return wrapped_print


# mock a discord.User int _author
_author = type("User", (object,), {"mention": "test_mention"})()
_send = print_("send")
_react = print_("react")
_persist = dict()
