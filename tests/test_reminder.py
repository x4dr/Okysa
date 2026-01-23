import sqlite3
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
import pytz

from Golconda import Reminder


@pytest.fixture
def mock_db_cursor():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    # Create table for testing
    cursor.executescript(
        "CREATE TABLE IF NOT EXISTS reminders ("
        "id integer PRIMARY KEY,"
        "channel int NOT NULL,"
        "executiondate DATE NOT NULL,"
        "message TEXT NOT NULL,"
        "mention TEXT NULL,"
        "every TEXT NULL);"
    )
    yield conn, cursor
    conn.close()


@pytest.fixture
def patch_reminddb(mock_db_cursor):
    conn, cursor = mock_db_cursor
    with patch("Golconda.Reminder.reminddb", conn):
        yield conn


def test_save_and_load_reminder(patch_reminddb):
    Reminder.save_reminder(1000.0, 123, "Test Msg", "@User", "1h")

    cur = patch_reminddb.cursor()
    rem = cur.execute("SELECT * FROM reminders").fetchone()
    assert rem[1] == 123
    assert rem[3] == "Test Msg"

    loaded = Reminder.loadreminder(rem[0])
    assert loaded[3] == "Test Msg"


def test_next_reminders(patch_reminddb):
    Reminder.save_reminder(100.0, 1, "First", "@U", "")
    Reminder.save_reminder(200.0, 1, "Second", "@U", "")

    nex = Reminder.next_reminders(1)
    assert len(nex) == 1
    assert nex[0][3] == "First"


def test_user_tz(mock_singleton):
    with patch("Golconda.Reminder.evilsingleton", return_value=mock_singleton):
        Reminder.set_user_tz(123, "Europe/Berlin")
        assert Reminder.get_user_tz(123) == "Europe/Berlin"


def test_new_reminder(patch_reminddb, mock_singleton, mock_user):
    with patch("Golconda.Reminder.evilsingleton", return_value=mock_singleton):
        mock_singleton.storage = {"reminder": {"123456789": {"tz": "UTC"}}}
        rem_time = Reminder.newreminder(mock_user, 987, "Test", "tomorrow", "None")
        assert rem_time > datetime.now(pytz.UTC)


def test_list_reminder(patch_reminddb):
    Reminder.save_reminder(100.0, 123, "Test Msg", "@User", "1h")
    rems = Reminder.listreminder(123)
    assert len(rems) == 1
    assert rems[0][3] == "Test Msg"


@pytest.mark.asyncio
async def test_remind_command_no_tz(mock_interaction, mock_singleton):
    with (
        patch("Commands.Remind.get_user_tz", side_effect=KeyError),
        patch("Commands.Remind.set_user_tz") as mock_set_tz,
        patch("Commands.Remind.newreminder", return_value="date"),
    ):
        mock_tree = MagicMock()
        from Commands import Remind

        Remind.register(mock_tree)
        remind_group = mock_tree.add_command.call_args[0][0]
        remind_me_cmd = next(c for c in remind_group.commands if c.name == "me")

        await remind_me_cmd.callback(mock_interaction, msg="hello")
        mock_set_tz.assert_called_with(mock_interaction.user.id, "Europe/Berlin")
        mock_interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_remind_tzset(mock_interaction):
    mock_tree = MagicMock()
    from Commands import Remind

    Remind.register(mock_tree)
    remind_group = mock_tree.add_command.call_args[0][0]
    tzset_cmd = next(c for c in remind_group.commands if c.name == "tzset")

    with patch("Commands.Remind.set_user_tz") as mock_set_tz:
        await tzset_cmd.callback(mock_interaction, tz="UTC")
        mock_set_tz.assert_called_with(mock_interaction.user.id, "UTC")
        mock_interaction.response.send_message.assert_called_with(
            "tz set to UTC", ephemeral=True
        )


@pytest.mark.asyncio
async def test_remindme_periodic(mock_singleton, mock_channel):
    # Use side_effect to return different values on consecutive calls to avoid infinite loop
    with (
        patch("Commands.Remind.evilsingleton", return_value=mock_singleton),
        patch(
            "Commands.Remind.next_reminders",
            side_effect=[
                [(1, 123, time.time() - 10, "msg", "@user", None)],
                [],
            ],
        ),
        patch("Commands.Remind.delreminder") as mock_del,
    ):
        mock_singleton.client.get_channel.return_value = mock_channel

        mock_tree = MagicMock()
        from Commands import Remind

        Remind.register(mock_tree)
        # The function is decorated with @call_periodically, we need to find it in Scheduling.functions
        from Golconda import Scheduling

        remindme_func = next(
            f[0] for f in Scheduling.functions if f[0].__name__ == "remindme"
        )

        await remindme_func()
        mock_channel.send.assert_called_with("@user  msg\n")
        mock_del.assert_called_with(1)
