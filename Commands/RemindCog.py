import asyncio
import logging
import time
from typing import Type

import dateutil.tz
import hikari

from Golconda.Reminder import next_reminders, delreminder, newreminder, set_user_tz
from Golconda.Scheduling import call_periodically
from Golconda.Slash import Slash

logger = logging.getLogger(__name__)


def register(slash: Type[Slash]):
    # noinspection PyUnusedLocal
    @slash.cmd("reminder", "set timestuff")
    async def base(cmd: Slash):
        ...  # no common code

    @call_periodically
    async def reminding(self):
        repeat = True
        while repeat:
            repeat = False  # probably wont pull reminders more than once
            nr = list(next_reminders())
            if nr:
                logger.info(f"reminding {nr}")
            for r in nr:  # pull the next relevant reminders
                delta = r[2] - time.time()
                logger.info(f"{delta=}")
                if delta > 60:
                    break  # nothing within a minute, we will be called again before it is time
                else:
                    logger.info(f"reminding {delta}, {r}")
                    await asyncio.sleep(delta)
                    # since reminders are in order we consume them in order
                    channel: hikari.TextableChannel = self.client.get_channel(r[1])
                    if not channel:
                        break  # not connected, try later
                    await channel.send(r[3])
                    delreminder(r[0])
            else:  # if we consume all within a minute, we need to pull more
                repeat = bool(nr)  # but only if there were reminders

    @slash.option("tz", "timezone in IANA format like Europe/Berlin")
    @slash.sub("tzset", "sets the timezone", of=base)
    async def tzset(cmd: Slash):
        try:
            assert dateutil.tz.gettz(cmd.get("tz"))
            set_user_tz(cmd.author.id, cmd.get("tz"))
            return await cmd.respond_instant_ephemeral("tz set to " + cmd.get("tz"))
        except ValueError:
            await cmd.respond_instant_ephemeral(
                cmd.author.mention
                + " Not a Valid TimeZone. Try Europe/Berlin or look up your IANA tzinfo online."
            )

    @slash.option("msg", "what to send to you")
    @slash.option("time", "when to remind")
    @slash.sub(
        "me",
        "set the reminder",
        of=base,
    )
    async def remind(cmd: Slash):
        try:
            newdate = newreminder(cmd.author, cmd.channel_id, cmd.get("msg"))
            await cmd.respond_instant("will remind on " + newdate.isoformat())
        except KeyError:
            set_user_tz(cmd.author.id, "Europe/Berlin")
            await cmd.respond_instant_ephemeral(
                "No timezone configured, automatically set to Europe/Berlin.\n"
                "Please use the command tzset with your timezone if you want to change it."
            )

    @slash.sub("del", "deletes (doesnt work yet)", of=base)
    async def remind_del(cmd: Slash):
        return await cmd.respond_instant_ephemeral("not done with this")
        # await delreminder(" ".join(msg))
        # ctx.send("deleted")

    """
    @slash.sub("list", "lists reminders set here", of=base)
    async def remind_list(cmd:Slash):
        toshow = ""
        for r in listreminder(cmd.channel_id):
            toshow += f"{datetime.datetime.fromtimestamp(int(r[2]), reference.LocalTimezone())}: {r[3]}\n"
    
        toshow = re.sub(r"<@!?(.*?)>", mentionreplacer(self.client), toshow)
        await ctx.channel.send("Reminders:\n" + toshow)
    
    
    def setup(client: commands.Bot):
        client.add_cog(RemindCog(client))
    """
