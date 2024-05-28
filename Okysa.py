import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands

import Commands
from Golconda.Rights import allowed, is_owner
from Golconda.Routing import main_route
from Golconda.Scheduling import periodic
from Golconda.Storage import setup, migrate, evilsingleton

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
Commands.register(tree)


@client.event
async def on_ready():
    await setup(client)
    await client.application.owner.send(f"I am {client.user}!")
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"prayers since {datetime.now().strftime('%H:%M %d.%m.%Y')}",
        )
    )

    # noinspection PyAsyncCall
    await periodic()


def configure_logging() -> None:
    log = logging.getLogger("root")
    log.setLevel(logging.INFO if "debug" not in sys.argv else logging.DEBUG)

    loc = ([x[4:] for x in sys.argv if x.startswith("log=")][:1] or ["./okysa.log"])[0]

    rfh = RotatingFileHandler(
        loc,
        maxBytes=521288,  # 512 KB
        encoding="utf-8",
        backupCount=10,
    )

    ff = logging.Formatter(
        "[%(asctime)s] %(levelname)s ||| %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    rfh.setFormatter(ff)
    log.addHandler(rfh)
    log.addHandler(logging.StreamHandler(sys.stdout))


if __name__ == "__main__":
    configure_logging()


@client.event
async def on_message(message: discord.Message):
    if message.channel.id == evilsingleton().bridge_channel:
        evilsingleton().store_message(message)
    if message.author != client.user and await allowed(message):
        await main_route(message)
        if "treesync" in message.content and is_owner(message.author):
            msg = ""
            for c in await tree.sync():
                msg += c.name + "\n"
            await message.channel.send(content=msg)
    elif (message.content or "").strip().startswith("?"):
        logging.error(f"not listening in {message.channel}")
    await migrate(client, message.author)
    for user in message.mentions:
        await migrate(client, user)


@client.event
async def on_raw_message_edit(event: discord.RawMessageUpdateEvent) -> None:
    channel = client.get_channel(event.channel_id)
    if channel:
        message = await channel.fetch_message(event.message_id)
        if message.author == client.user or not await allowed(message):
            return
        await main_route(message)


@client.event
async def on_raw_message_delete(event: discord.RawMessageDeleteEvent) -> None:
    channel = client.get_channel(event.message_id)
    if not channel:
        return
    message = channel.get_partial_message(event.message_id)
    d = 0.5
    async for m in channel.history(
        limit=10, after=message.created_at, oldest_first=True
    ):
        if m.author == client.user and m.reference.message_id == message.id:
            await m.delete(delay=d)
            d += 0.5


if __name__ == "__main__":
    with open(os.path.expanduser("~/token.discord"), "r") as tokenfile:
        token = tokenfile.read().strip()
        logging.debug("\n\n\n")
        client.run(token)
