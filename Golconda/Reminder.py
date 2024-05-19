import pathlib
import sqlite3
from datetime import datetime
from typing import List, Tuple

import dateparser
import discord
import pytz
from discord import app_commands

from Golconda.Storage import evilsingleton

last = {}
delete = []


def setup_db():
    path = pathlib.Path(__file__).parent / "remind.db"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE IF NOT EXISTS reminders ("
        "id integer PRIMARY KEY,"
        "channel int NOT NULL,"
        "executiondate DATE NOT NULL,"
        "message TEXT NOT NULL,"
        "mention TEXT NULL,"
        "every TEXT NULL);"
    )
    return con


reminddb = setup_db()


def next_reminders(num: int = 3) -> List[Tuple[int, int, int, int, str, str]]:
    cur = reminddb.cursor()
    return cur.execute(
        "SELECT id, channel, executiondate, message, mention, every FROM reminders ORDER BY executiondate LIMIT ?",
        (num,),
    ).fetchall()


def save_reminder(date: float, channel: int, message: str, mention: str, every: str):
    cur = reminddb.cursor()
    cur.execute(
        "INSERT INTO reminders(executiondate,channel,message,mention,every) VALUES (?,?,?,?,?)",
        (date, channel, message, mention, every),
    )
    reminddb.commit()


def set_user_tz(user: int, tzname: str):
    reminderstore = evilsingleton().storage.setdefault("reminder", {})
    u = reminderstore.setdefault(str(user), {})
    u["tz"] = tzname
    evilsingleton().write()


def get_user_tz(user: int) -> str:
    reminderstore = evilsingleton().storage.setdefault("reminder", {})
    if tzname := reminderstore.get(str(user)):
        return tzname["tz"]
    raise KeyError("no timezone!")


def newreminder(
    author: discord.User, channel_id: int, msg: str, target_time: str, every: str
) -> datetime:
    remind_time = dateparser.parse(
        target_time,
        languages=["en", "de"],
        settings={
            "TIMEZONE": get_user_tz(author.id),
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )

    if not remind_time:
        raise ValueError(f"{target_time} was not understood")
    save_reminder(remind_time.timestamp(), channel_id, msg, author.mention, every)
    return remind_time


def delreminder(reminder_id):
    cur = reminddb.cursor()
    cur.execute(
        "DELETE FROM reminders WHERE id=?",
        (reminder_id,),
    )
    reminddb.commit()


def loadreminder(reminder_id) -> Tuple[int, int, float, str, str, str]:
    cur = reminddb.cursor()
    return cur.execute(
        "SELECT id, channel, executiondate, message, mention, every FROM reminders WHERE id=?",
        (reminder_id,),
    ).fetchone()


def reschedule(reminder_id):
    cur = reminddb.cursor()
    date, raw_delta = cur.execute(
        "SELECT executiondate, every FROM reminders WHERE id=?",
        (reminder_id,),
    ).fetchone()
    delta = datetime.now() - dateparser.parse(raw_delta)
    delta = abs(delta)
    date = datetime.fromtimestamp(date)
    date += delta
    newdate = date.timestamp()
    cur.execute(
        "UPDATE reminders SET executiondate=? WHERE id=?", (newdate, reminder_id)
    )
    reminddb.commit()
    return date


def listreminder(channel_id: int) -> List[Tuple[int, int, float, str, str]]:
    cur = reminddb.cursor()
    return cur.execute(
        "SELECT id, channel, executiondate, message, mention, every FROM reminders WHERE channel=?",
        (channel_id,),
    ).fetchall()


async def reminder_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice]:
    choices = []
    for rem in listreminder(interaction.channel_id):
        if rem[4] == interaction.user.mention:
            choices.append(
                (
                    rem[3][:20]
                    + " @ "
                    + datetime.fromtimestamp(
                        rem[2], tz=pytz.timezone(get_user_tz(interaction.user.id))
                    ).strftime("%d.%m.%Y %H:%M:%S"),
                    str(rem[0]),
                )
            )
    return [app_commands.Choice(name=x[0], value=x[1]) for x in choices]


if __name__ == "__main__":
    setup_db()
