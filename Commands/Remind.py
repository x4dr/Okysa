import logging
import re
from datetime import datetime

import dateutil.tz
import discord
from discord import app_commands

from Golconda.Reminder import (
    next_reminders,
    delreminder,
    newreminder,
    set_user_tz,
    listreminder,
    get_user_tz,
    reschedule,
    reminder_autocomplete,
    loadreminder,
)
from Golconda.Scheduling import call_periodically
from Golconda.Storage import evilsingleton
from Golconda.Tools import mentionreplacer

logger = logging.getLogger(__name__)


def register(tree: discord.app_commands.CommandTree):
    # noinspection PyUnusedLocal
    group = app_commands.Group(name="remind", description="set reminders")

    @group.command(name="tzset", description="sets the timezone")
    async def tzset(interaction: discord.Interaction, tz: str = None):
        try:
            assert dateutil.tz.gettz(tz)
            set_user_tz(interaction.user.id, tz)
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(f"tz set to {tz}", ephemeral=True)
        except ValueError:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                f"{interaction.user.mention} Not a Valid TimeZone. "
                f"Try Europe/Berlin or look up your IANA tzinfo online.",
                ephemeral=True,
            )

    @group.command(name="me", description="set the reminder")
    @app_commands.describe(
        msg="what to send to you",
        when="when to remind ('in 1h' or '1. april 9:00')",
        every="interval to repeat reminder (1h / 1 day)",
    )
    async def remind(
        interaction: discord.Interaction, msg: str, when: str = None, every: str = None
    ):
        try:
            get_user_tz(interaction.user.id)
        except KeyError:
            set_user_tz(interaction.user.id, "Europe/Berlin")
            # noinspection PyUnresolvedReferences
            await interaction.channel.send_message(
                "No timezone configured, automatically set to Europe/Berlin.\n"
                "Please use the command tzset with your timezone if you want to change it.",
                ephemeral=True,
            )
        if not when:
            when = "in 1h"
        newdate = newreminder(
            interaction.user, interaction.channel_id, msg, when, every
        )
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message(f"will remind on {newdate}")

    @app_commands.describe(which="which reminder to delete")
    @group.command(
        name="delete", description="deletes a reminder, use the autocompletion"
    )
    @app_commands.autocomplete(which=reminder_autocomplete)
    async def remind_del(interaction: discord.Interaction, which: str = None):
        if loadreminder(which)[4] == interaction.user.mention:
            delreminder(which)
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("deleted", delete_after=3)

    @group.command(name="list", description="lists reminders set here")
    async def remind_list(interaction: discord.Interaction):
        toshow = ""
        for r in listreminder(interaction.channel_id):
            toshow += f"{datetime.fromtimestamp(int(r[2]))}: {r[3]}\n"

        toshow = re.sub(r"<@!?(.*?)>", mentionreplacer(interaction.client), toshow)
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("Reminders:\n" + toshow)

    @group.command(name="upcoming", description="lists upcoming reminders")
    async def remind_upcoming(interaction: discord.Interaction):
        toshow = ""
        for r in next_reminders(10):
            toshow += f"{datetime.fromtimestamp(int(r[2])).strftime('%d.%m.%Y %H:%M:%S')}: {r[3]}\n"

        toshow = re.sub(r"<@!?(.*?)>", mentionreplacer(interaction.client), toshow)
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("Reminders:\n" + toshow)

    tree.add_command(group)

    @call_periodically
    async def remindme():
        s = evilsingleton()
        workdone = True
        time_to_next = 15
        while workdone:
            workdone = False
            for (
                remid,
                channel,
                executiondate,
                message,
                mention,
                every,
            ) in next_reminders(10):
                when = executiondate - datetime.now().timestamp()
                if when <= 0:
                    workdone = True
                    channel = s.client.get_channel(channel)
                    toshow = f"{mention}  {message}\n"
                    if not every:
                        delreminder(remid)
                    else:
                        newdate = reschedule(remid)
                        toshow += f"\n next reminder: {newdate.strftime('%d.%m.%Y %H:%M:%S')} use /remind delete to stop"
                    await channel.send(toshow)
                else:
                    time_to_next = min(time_to_next, when)
        return time_to_next
