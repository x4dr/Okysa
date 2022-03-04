import re

import hikari

from Golconda.Storage import getstorage

discordid = re.compile(r"<@!(\d+)>")


async def invoke(message):
    storage = getstorage()
    if message.channel_id not in storage.allowed_channels:
        storage.allowed_channels.append(message.channel_id)
        storage.write()
        await message.respond("i will now listen here, banish me ")
    await message.add_reaction("\N{THUMBS UP SIGN}")


async def banish(message):
    if "BANISH" in message.content:
        storage = getstorage()
        storage.allowed_channels.remove(message.channel_id)
        storage.write()
        await message.add_reaction("\N{THUMBS UP SIGN}")


async def who_am_i(message):
    try:
        await message.respond(
            "You are " f"{getstorage().storage[str(message.author)]['NossiAccount']}"
        )
    except KeyError:
        await message.respond("No Idea")


async def i_am(message, person):
    s = getstorage()
    d = s.storage.setdefault(str(message.author), {"defines": {}})
    d["NossiAccount"] = person.upper()
    d["DiscordAccount"] = str(message.author)
    await message.add_reaction("\N{THUMBS UP SIGN}")
    s.write()


def message_prep(message: hikari.Message) -> list[str]:
    msg = message.content.lower().strip("` ")
    storage = getstorage()
    selfname = storage.me.username.lower()
    if msg.lower().startswith(selfname):
        msg = msg[len(selfname) :]
    return [x for x in msg.split() if x]
