import discord
from gamepack.Dice import DescriptiveError

from Commands.Base import message_prep, banish, invoke, make_bridge
from Golconda.Rights import is_owner
from Golconda.RollInterface import rollhandle
from Golconda.Storage import evilsingleton
from Golconda.Tools import (
    define,
    undefine,
    mutate_message,
    split_send,
    get_remembering_send,
)

paths = {}


def default(func=None):
    if func is None:
        return paths.default
    paths.default = func
    return func


def command(cmd, prefix=None):
    if prefix is None:
        return paths.get(cmd, default())
    paths[prefix] = cmd
    return cmd


async def main_route(message: discord.Message) -> None:
    s = evilsingleton()

    for m in message_prep(message):
        match m:
            case ["die"] if message.content.strip() == "DIE":  # upper case only
                if is_owner(message.author):
                    await message.add_reaction("\U0001f480")
                    await evilsingleton().client.close()
            case ["banish"]:
                await banish(message)
            case ["make", "bridge"]:
                if not await make_bridge(message):
                    await message.reply("nope!")
            case ["invoke"]:
                await invoke(message)
            case ["def", *rest]:
                await define(
                    " ".join(rest),
                    message,
                    s.storage.setdefault(str(message.author.id), {}),
                )
                s.write()
            case ["undef", *rest]:
                await undefine(
                    " ".join(rest),
                    message.add_reaction,
                    s.storage.setdefault(str(message.author.id), {}),
                )
                s.write()
            case roll:
                try:
                    roll, dbg = await mutate_message(
                        " ".join(roll), s.storage.setdefault(str(message.author.id), {})
                    )
                    if dbg and len(dbg) > 1950:
                        await split_send(message.reply, dbg.splitlines())
                    elif dbg:
                        await message.reply(dbg)
                except DescriptiveError as e:
                    await message.author.send(e.args[0])

                await rollhandle(
                    roll,
                    message,
                    get_remembering_send(message),
                    message.add_reaction,
                    evilsingleton().storage,
                )
