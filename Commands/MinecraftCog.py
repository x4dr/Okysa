import subprocess

import hikari

from Golconda.Slashing import Slash
from Golconda.Storage import getstorage


@Slash.option("person", "mention", hikari.OptionType.USER, required=False)
@Slash.option("command", "What to do", choices=["up", "reg"])
@Slash.cmd("mc", "Minecraft control")
async def mccmd(cmd: Slash):
    task = cmd.get("command")
    options = {"up": mcup, "reg": register_user}
    await options[task](cmd)


async def mcup(cmd: Slash):
    if cmd.user.id in getstorage().storage.get("mc_powerusers", []):
        await cmd.respond_instant("Booting Server!")
        subprocess.call(["mcstart"])
    else:
        await cmd.respond_instant("Access Denied!")


@Slash.owner()
async def register_user(cmd: Slash):
    u: hikari.User = cmd.get("person")
    s = getstorage()
    registered = s.storage.get("mc_powerusers", [])
    if u.id in registered:
        registered.remove(u.id)
        await cmd.respond_instant(f"Removed {u} from allowed users.")
    else:
        registered.append(u.id)
        await cmd.respond_instant(f"Added {u} to allowed users.")
    s.storage["mc_powerusers"] = registered
    s.write()
