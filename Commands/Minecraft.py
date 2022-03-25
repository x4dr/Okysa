import subprocess
from typing import Type

import hikari

from Golconda.Slash import Slash
from Golconda.Storage import evilsingleton


def register(slash: Type[Slash]):
    # noinspection PyUnusedLocal
    @slash.cmd("minecraftserver", "Minecraft control")
    async def mccmd(cmd: Slash):
        print("called mccmd!")

    @slash.sub("up", "brings the server up", mccmd)
    async def mcup(cmd: Slash):
        if cmd.author.id in evilsingleton().storage.get("mc_powerusers", []):
            await cmd.respond_instant("Booting Server!")
            subprocess.call(["mcstart"])
        else:
            await cmd.respond_instant("Access Denied!")

    @slash.owner()
    @slash.option("person", "mention", hikari.OptionType.USER, required=False)
    @slash.sub("reg", "(un)register a new authorized user", mccmd)
    async def register_user(cmd: Slash):
        u: hikari.User = cmd.get("person")
        s = evilsingleton()
        registered = s.storage.get("mc_powerusers", [])
        if u in registered:
            registered.remove(u)
            await cmd.respond_instant(f"Removed {u} from allowed users.")
        else:
            registered.append(u)
            await cmd.respond_instant(f"Added {u} to allowed users.")
        s.storage["mc_powerusers"] = registered
        s.write()
