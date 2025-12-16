import discord

from Commands.Base import message_prep, banish, invoke, make_bridge
from Golconda.Rights import is_owner
from Golconda.RollInterface import rollhandle, AuthorError

from Golconda.Tools import (
    define,
    undefine,
    get_remembering_send,
)
from Golconda.eastereggs import eastereggs

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
    storage = message.client.storage

    for m in message_prep(message.content, message.client.user.name):
        match m:
            case ["DIE"]:
                if is_owner(message.author, message.client):
                    await message.add_reaction("💀")
                    await message.client.close()
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
                    storage.storage.setdefault(str(message.author.id), {}),
                )
                storage.write()
            case ["undef", *rest]:
                await undefine(
                    " ".join(rest),
                    message.add_reaction,
                    storage.storage.setdefault(str(message.author.id), {}),
                )
                storage.write()
            case roll:
                msg = " ".join(roll)
                if message.webhook_id:
                    mention = "@" + str(message.author.name)
                else:
                    mention = message.author.mention
                try:
                    if (
                        await rollhandle(
                            msg,
                            mention,
                            get_remembering_send(message),
                            message.add_reaction,
                            storage,
                        )
                    ) is None:
                        await eastereggs(message)
                except AuthorError as e:
                    await message.author.send(e.args[0])
