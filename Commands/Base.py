import re
from typing import Type, Generator

import hikari

from Golconda.Slash import Slash
from Golconda.Storage import evilsingleton

discordid = re.compile(r"<@!(\d+)>")


async def invoke(message):
    storage = evilsingleton()
    if message.channel_id not in storage.allowed_channels:
        storage.allowed_channels.append(message.channel_id)
        storage.write()
        await message.respond("i will now listen here, until someone banishes me.")
    await message.add_reaction("\N{THUMBS UP SIGN}")


async def banish(message):
    if "BANISH" in message.content:
        storage = evilsingleton()
        storage.allowed_channels.remove(message.channel_id)
        storage.write()
        await message.add_reaction("\N{THUMBS UP SIGN}")


def message_prep(message: hikari.Message) -> Generator[list[str], None, None]:
    for msg in (message.content or "").split("\n"):
        msg = re.sub(r"<@[!&]?\d{18}>", "", msg).lower().strip("` ")
        storage = evilsingleton()
        selfname = storage.me.username.lower()
        if msg.lower().startswith(selfname):
            msg = msg[len(selfname) :]
        yield [x for x in msg.split() if x]


def register(slash: Type[Slash]):
    @slash.cmd("whoami", "gets the currently configured NosferatuNetwork account name")
    async def who_am_i(cmd: Slash):
        try:
            await cmd.respond_instant_ephemeral(
                "You are "
                f"{evilsingleton().storage[str(cmd.author)]['NossiAccount']}."
            )
        except KeyError:
            await cmd.respond_instant_ephemeral("No Idea")

    @slash.option("say", "the message that will be posted")
    @slash.cmd("anon", "say something anonymously")
    async def anon(cmd: Slash):
        if say := cmd.get("say"):
            c = await cmd.fetch_channel()
            await cmd.respond_instant_ephemeral("send message anonymously")
            await c.send(f"anon: {say}")

    @slash.option("nossiaccount", "your name on the NosferatuNet", required=False)
    @slash.cmd("register", "sets up the connection to the NosferatuNetwork")
    async def i_am(cmd: Slash):
        s = evilsingleton()
        d = s.storage.setdefault(str(cmd.author), {"defines": {}})
        if not cmd.get("nossiaccount"):
            d.pop("NossiAccount")
            await cmd.respond_instant_ephemeral("... Who are you?")
        else:
            d["NossiAccount"] = cmd.get("nossiaccount").upper()
            d["DiscordAccount"] = str(cmd.author)
            await cmd.respond_instant_ephemeral(
                f"I have saved your account as {d['NossiAccount']}."
            )
        s.write()
