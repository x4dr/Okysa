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
)
from Golconda.Scheduling import call_periodically
from Golconda.Storage import evilsingleton
from Golconda.Tools import mentionreplacer

logger = logging.getLogger(__name__)


def register(tree: discord.app_commands.CommandTree):
    # noinspection PyUnusedLocal
    group = app_commands.Group(name="reminder", description="set reminders")

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

    @app_commands.describe(msg="what to send to you", time="when to remind")
    @group.command(name="me", description="set the reminder")
    async def remind(
        interaction: discord.Interaction,
        msg: str = None,
    ):
        try:
            newdate = newreminder(interaction.user, interaction.channel_id, msg)
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                f"will remind on {newdate.isoformat()}"
            )
        except KeyError:
            set_user_tz(interaction.user.id, "Europe/Berlin")
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                "No timezone configured, automatically set to Europe/Berlin.\n"
                "Please use the command tzset with your timezone if you want to change it.",
                ephemeral=True,
            )

    @app_commands.describe(which="which reminder to delete")
    @group.command(name="del", description="deletes (doesnt work yet)")
    async def remind_del(interaction: discord.Interaction, which: str = None):
        #  noinspection PyUnresolvedReferences
        await interaction.response.send_message("not done with this", ephemeral=True)
        await delreminder(which)
        # noinspection PyUnresolvedReferences
        await interaction.response.send("deleted")

    # a set of commands to manage reminders
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
            toshow += f"{datetime.fromtimestamp(int(r[2]))}: {r[3]}\n"

        toshow = re.sub(r"<@!?(.*?)>", mentionreplacer(interaction.client), toshow)
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("Reminders:\n" + toshow)

    tree.add_command(group)

    @call_periodically(60)
    async def remindme():
        for channel, executiondate, message, mention in next_reminders(10):
            s = evilsingleton()
            channel = s.client.get_channel(channel)
            toshow = f"{datetime.fromtimestamp(int(executiondate))}: {message}\n"
            toshow = re.sub(r"<@!?(.*?)>", mentionreplacer(mention), toshow)
            await channel.send(toshow)
