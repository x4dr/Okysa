import logging
import re
from datetime import datetime
from typing import Optional, List, Tuple

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


class RemindCommand:
    """Manage your personal and group reminders.

    Commands:
    - remind tzset <timezone>: Set your timezone (e.g., Europe/Berlin).
    - remind me <msg> [when] [every]: Set a reminder.
    - remind delete <id>: Delete a reminder.
    - remind list: List reminders in this channel.
    - remind upcoming: List next 10 upcoming reminders.

    Tip: Use ?remind <command> for parameter details.
    """

    @staticmethod
    async def handle(ctx, args: list[str]) -> None:
        if len(args) < 2:
            return

        subcommand = args[1].lower()
        match subcommand:
            case "tzset":
                tz = args[2] if len(args) > 2 else None
                await ctx.reply(RemindCommand.tzset_logic(str(ctx.author.id), tz))
            case "me":
                if len(args) < 3:
                    await ctx.reply("Usage: remind me <msg> [when] [every]")
                    return
                # Simple parsing for text: me <msg> [when] [every]
                msg = args[2]
                when = args[3] if len(args) > 3 else None
                every = args[4] if len(args) > 4 else None
                await ctx.reply(
                    RemindCommand.remind_me_logic(
                        ctx.author, int(ctx.channel.id or 0), msg, when, every
                    )
                )
            case "delete":
                rem_id = args[2] if len(args) > 2 else None
                await ctx.reply(RemindCommand.delete_logic(ctx.author.mention, rem_id))
            case "list":
                reminders = RemindCommand.list_logic(int(ctx.channel.id or 0))
                toshow = "Reminders:\n"
                for ts, msg in reminders:
                    toshow += f"{datetime.fromtimestamp(int(ts))}: {msg}\n"
                await ctx.reply(toshow)
            case "upcoming":
                reminders = RemindCommand.upcoming_logic(10)
                toshow = "Upcoming Reminders:\n"
                for ts, msg in reminders:
                    toshow += f"{datetime.fromtimestamp(int(ts)).strftime('%d.%m.%Y %H:%M:%S')}: {msg}\n"
                await ctx.reply(toshow)

    @staticmethod
    def tzset_logic(user_id: str, tz: Optional[str]) -> str:
        """Set your timezone (e.g., Europe/Berlin).
        Usage: remind tzset <timezone>
        """
        if tz is None:
            return "Please provide a timezone."
        try:
            assert dateutil.tz.gettz(tz)
            set_user_tz(user_id, tz)
            return f"tz set to {tz}"
        except ValueError, AssertionError:
            return "Not a Valid TimeZone. Try Europe/Berlin or look up your IANA tzinfo online."

    @staticmethod
    def remind_me_logic(
        user: Any, channel_id: int, msg: str, when: Optional[str], every: Optional[str]
    ) -> str:
        """Set a reminder.
        Usage: remind me <msg> [when] [every]
        - <msg>: What to send to you.
        - [when]: Optional. 'in 1h' or '1. april 9:00'. Default: in 1h.
        - [every]: Optional. Interval to repeat (e.g., 1h, 1 day).
        """
        try:
            get_user_tz(user.id)
            prefix = ""
        except KeyError:
            set_user_tz(user.id, "Europe/Berlin")
            prefix = "No timezone configured, automatically set to Europe/Berlin.\nPlease use the command tzset with your timezone if you want to change it.\n"

        if not when:
            when = "in 1h"
        newdate = newreminder(user, channel_id, msg, when, every or "")
        return f"{prefix}will remind on {newdate}"

    @staticmethod
    def delete_logic(user_mention: str, rem_id: Optional[str]) -> str:
        """Delete a reminder.
        Usage: remind delete <id>
        - <id>: The reminder ID to delete.
        """
        if rem_id is None:
            return "Please provide a reminder id."
        rem = loadreminder(rem_id)
        if rem and rem[4] == user_mention:
            delreminder(rem_id)
            return "deleted"
        return "Reminder not found or access denied."

    @staticmethod
    def list_logic(channel_id: int) -> List[Tuple[float, str]]:
        """List reminders in this channel."""
        return [(float(r[2]), str(r[3])) for r in listreminder(channel_id)]

    @staticmethod
    def upcoming_logic(count: int = 10) -> List[Tuple[float, str]]:
        """List upcoming reminders globally."""
        return [(float(r[2]), str(r[3])) for r in next_reminders(count)]


def register(tree: discord.app_commands.CommandTree) -> None:
    group = app_commands.Group(name="remind", description="set reminders")

    @group.command(name="tzset", description="sets the timezone")
    async def tzset(interaction: discord.Interaction, tz: str | None = None) -> None:
        res = RemindCommand.tzset_logic(str(interaction.user.id), tz)
        await interaction.response.send_message(res, ephemeral=True)

    @group.command(name="me", description="set the reminder")
    @app_commands.describe(
        msg="what to send to you",
        when="when to remind ('in 1h' or '1. april 9:00')",
        every="interval to repeat reminder (1h / 1 day)",
    )
    async def remind(
        interaction: discord.Interaction,
        msg: str,
        when: str | None = None,
        every: str | None = None,
    ) -> None:
        res = RemindCommand.remind_me_logic(
            interaction.user, interaction.channel_id or 0, msg, when, every
        )
        await interaction.response.send_message(res)

    @app_commands.describe(which="which reminder to delete")
    @group.command(
        name="delete", description="deletes a reminder, use the autocompletion"
    )
    @app_commands.autocomplete(which=reminder_autocomplete)
    async def remind_del(
        interaction: discord.Interaction, which: str | None = None
    ) -> None:
        res = RemindCommand.delete_logic(interaction.user.mention, which)
        await interaction.response.send_message(
            res, ephemeral=True if res != "deleted" else False
        )

    @group.command(name="list", description="lists reminders set here")
    async def remind_list(interaction: discord.Interaction) -> None:
        reminders = RemindCommand.list_logic(interaction.channel_id or 0)
        toshow = "Reminders:\n"
        for ts, msg in reminders:
            toshow += f"{datetime.fromtimestamp(int(ts))}: {msg}\n"
        if interaction.client:
            toshow = re.sub(r"<@!?(.*?)>", mentionreplacer(interaction.client), toshow)
        await interaction.response.send_message(toshow)

    @group.command(name="upcoming", description="lists upcoming reminders")
    async def remind_upcoming(interaction: discord.Interaction) -> None:
        reminders = RemindCommand.upcoming_logic(10)
        toshow = "Reminders:\n"
        for ts, msg in reminders:
            toshow += f"{datetime.fromtimestamp(int(ts)).strftime('%d.%m.%Y %H:%M:%S')}: {msg}\n"
        if interaction.client:
            toshow = re.sub(r"<@!?(.*?)>", mentionreplacer(interaction.client), toshow)
        await interaction.response.send_message(toshow)

    tree.add_command(group)

    @call_periodically
    async def remindme() -> float:
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
                    channel_obj = s.client.get_channel(channel)
                    toshow = f"{mention}  {message}\n"
                    if not every:
                        delreminder(remid)
                    else:
                        newdate = reschedule(remid)
                        toshow += f"\n next reminder: {newdate.strftime('%d.%m.%Y %H:%M:%S')} use /remind delete to stop"
                    if isinstance(channel_obj, discord.abc.Messageable):
                        await channel_obj.send(toshow)
                else:
                    time_to_next = min(time_to_next, when)
        return time_to_next
