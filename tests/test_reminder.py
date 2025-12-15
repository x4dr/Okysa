import pytest
from unittest.mock import patch
from Golconda import Reminder
import sqlite3


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
    Reminder.save_reminder(100.0, 1, "First", "@U", None)
    Reminder.save_reminder(200.0, 1, "Second", "@U", None)

    nex = Reminder.next_reminders(1)
    assert len(nex) == 1
    assert nex[0][3] == "First"


def test_del_reminder(patch_reminddb):
    Reminder.save_reminder(100.0, 1, "Msg", "@U", None)
    cur = patch_reminddb.cursor()
    remid = cur.execute("SELECT id FROM reminders").fetchone()[0]

    Reminder.delreminder(remid)
    rem = cur.execute("SELECT * FROM reminders").fetchall()
    assert len(rem) == 0
