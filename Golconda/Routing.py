import time
from typing import cast

import hikari

from Commands.Base import message_prep, discordid, banish, invoke
from Golconda.Rights import is_owner
from Golconda.RollInterface import rollhandle
from Golconda.Sound import stream_sound, stop_stream, restream
from Golconda.Storage import getstorage
from Golconda.Tools import define, undefine, mutate_message

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


async def main_route(event: hikari.MessageEvent) -> None:
    t1 = time.perf_counter()
    message: hikari.Message = event.message
    bot: hikari.GatewayBot = cast(message.app, hikari.GatewayBot)

    gid = message.guild_id
    author = event.author
    s = getstorage()
    t2 = time.perf_counter()
    match message_prep(message):
        case ["join", person, *_]:
            print(f"join {person}")
            m = discordid.match(person)
            user = int(m.group(0)) if m else author
            await stream_sound(author, bot, gid, user)
        case ["sync", *_]:
            await restream()
        case ["leave", *_]:
            await stop_stream(bot, gid)
        case ["die", *_]:
            if is_owner(message.author):
                await message.add_reaction("\U0001f480")
                exit()
        case ["banish"]:
            await banish(message)
        case ["invoke", *_]:
            await invoke(message)
        case ["def", *rest]:
            await define(" ".join(rest), message, s.storage.setdefault(str(author), {}))
            s.write()
        case ["undef", *rest]:
            await undefine(
                " ".join(rest), message, s.storage.setdefault(str(author), {})
            )
            s.write()
        case roll:
            roll = await mutate_message(
                " ".join(roll), s.storage.setdefault(str(author), {})
            )
            await rollhandle(
                roll,
                author,
                message.respond,
                message.add_reaction,
                getstorage().storage,
            )
    print("main_route", time.perf_counter()-t2, t2-t1)
