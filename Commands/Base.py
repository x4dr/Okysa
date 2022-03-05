import re

import hikari

from Golconda.Slashing import Slash
from Golconda.Storage import getstorage

discordid = re.compile(r"<@!(\d+)>")


async def invoke(message):
    storage = getstorage()
    if message.channel_id not in storage.allowed_channels:
        storage.allowed_channels.append(message.channel_id)
        storage.write()
        await message.respond("i will now listen here, until someone banishes me.")
    await message.add_reaction("\N{THUMBS UP SIGN}")


async def banish(message):
    if "BANISH" in message.content:
        storage = getstorage()
        storage.allowed_channels.remove(message.channel_id)
        storage.write()
        await message.add_reaction("\N{THUMBS UP SIGN}")


@Slash.cmd("whoami", "gets the currently configured NosferatuNetwork account name")
async def who_am_i(cmd: Slash):
    try:
        await cmd.respond_instant_ephemeral(
            "You are " f"{getstorage().storage[str(cmd.user)]['NossiAccount']}."
        )
    except KeyError:
        await cmd.respond_instant_ephemeral("No Idea")


def message_prep(message: hikari.Message) -> list[str]:
    msg = message.content.lower().strip("` ")
    storage = getstorage()
    selfname = storage.me.username.lower()
    if msg.lower().startswith(selfname):
        msg = msg[len(selfname) :]
    return [x for x in msg.split() if x]


@Slash.option("say", "the message that will be posted")
@Slash.cmd("anon", "say something anonymously")
async def anon(cmd: Slash):
    if say := cmd.get("say"):

        c = await cmd.fetch_channel()
        await c.send(f"anon:{say}")


@Slash.option("NossiAccount", "your name on the NosferatuNet")
@Slash.cmd("iam", "sets up the connection to the NosferatuNetwork")
async def i_am(cmd: Slash):
    s = getstorage()
    d = s.storage.setdefault(str(cmd.user), {"defines": {}})
    d["NossiAccount"] = cmd.get("NosferatuNet Account").upper()
    d["DiscordAccount"] = str(cmd.user)
    await cmd.respond_instant_ephemeral(
        f"I have saved your account as {d['NossiAccount']}."
    )
    s.write()
