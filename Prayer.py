import os
import re
from pathlib import Path
from typing import Iterable

import hikari

from Pantheon.Ateph import setup, get_storage
from Pantheon.ShiningOne import allowed, is_owner
from Pantheon.misc import stream_sound, restream, stop_stream
from old.RollInterface import rollhandle
from old.Tools import discordname

if os.name != "nt":
    import uvloop

    uvloop.install()

with open(os.path.expanduser("~/token.discord"), "r") as tokenfile:
    bot = hikari.GatewayBot(token=tokenfile.read().strip())

discordid = re.compile(r"<@!(\d+)>")


@bot.listen(hikari.StartedEvent)
async def startup(event: hikari.StartedEvent):
    print("STARTED")
    await setup(bot, Path("~/pray.pickle"))


def message_prep(message: hikari.Message) -> list[str]:
    msg = message.content.lower().strip()
    storage = get_storage()
    selfname = storage.me.username.lower()
    if msg.lower().startswith(selfname):
        msg = msg[len(selfname) :]
    return [x for x in msg.split() if x]


async def main_route(event: hikari.MessageEvent) -> str | None:
    message: hikari.Message = event.message
    gid = message.guild_id
    author = event.author
    print(f">>\n{message.content}\n{message_prep(message)}\n<<")

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
        case ["i", "am", person, *_] | ["iam", person, *_]:
            await i_am(message, person)
        case ["who", "am", "i", *_] | ["whoami", *_]:
            await who_am_i(message)
        case ["banish"]:
            await banish(message)
        case ["invoke", *_]:
            await invoke(message)
        case roll:
            await rollhandle(
                roll,
                author,
                message.respond,
                message.add_reaction,
                get_storage().storage,
            )


async def invoke(message):
    storage = get_storage()
    if message.channel_id not in storage.allowed_channels:
        storage.allowed_channels.append(message.channel_id)
        storage.write()
        await message.respond("i will now listen here, banish me ")
    await message.add_reaction("\N{THUMBS UP SIGN}")


async def banish(message):
    if "BANISH" in message.content:
        storage = get_storage()
        storage.allowed_channels.remove(message.channel_id)
        storage.write()
        await message.add_reaction("\N{THUMBS UP SIGN}")


async def who_am_i(message):
    try:
        await message.respond(
            "You are "
            f"{get_storage().storage[discordname(message.author)]['NossiAccount']}"
        )
    except KeyError:
        await message.respond("No Idea")


async def i_am(message, person):
    storage = get_storage()
    if storage.storage.get(discordname(message.author)) is None:
        storage.storage[discordname(message.author)] = {"defines": {}}
    storage.storage[discordname(message.author)]["NossiAccount"] = person.upper()
    await message.add_reaction("\N{THUMBS UP SIGN}")
    storage.write()


@bot.listen()
async def on_message(event: hikari.MessageCreateEvent) -> None:
    """Listen for messages being created."""
    # Do not respond to bots or webhooks!
    if not event.is_human or not await allowed(event.message):
        await route(event)


if __name__ == "__main__":
    print("starting...")
    bot.run()
