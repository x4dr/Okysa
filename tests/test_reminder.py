import sqlite3
from datetime import datetime
from unittest.mock import patch

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
async def test_reminder_autocomplete(mock_interaction, patch_reminddb, mock_singleton):
    with patch("Golconda.Reminder.evilsingleton", return_value=mock_singleton):
        mock_singleton.storage = {"reminder": {"123456789": {"tz": "UTC"}}}
        channel_id = 987654321
        mock_interaction.channel_id = channel_id
        Reminder.save_reminder(
            100.0, channel_id, "Test", mock_interaction.user.mention, "1h"
        )
        res = await Reminder.reminder_autocomplete(mock_interaction, "")
        assert len(res) == 1
        assert "Test" in res[0].name
