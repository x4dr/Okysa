import pytest
from unittest.mock import MagicMock, patch
from Golconda import Storage
import sqlite3
import os


@pytest.fixture
def mock_env(tmp_path):
    storage_file = tmp_path / "storage.json"
    storage_file.write_text("{}")

    db_file = tmp_path / "obsidian.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE configs (user text, option text, value text);")
    conn.close()

    env = {
        "NOSSI": "nossinet.cc",
        "OLLAMA": "http://localhost:11434",
        "DATABASE": str(db_file),
        "WIKI": str(tmp_path / "Wiki"),
        "STORAGE": str(storage_file),
    }
    with patch.dict(os.environ, env):
        yield env, storage_file, db_file


def test_storage_init(mock_env):
    env, s_file, db_file = mock_env
    client = MagicMock()

    with patch("Golconda.Storage.WikiPage"):
        s = Storage.Storage(client)
        assert s.nossilink == "nossinet.cc"
        assert s.db is not None
        assert s.storage == {}


def test_storage_read_write(mock_env):
    env, s_file, db_file = mock_env
    client = MagicMock()

    with patch("Golconda.Storage.WikiPage"):
        s = Storage.Storage(client)
        s.storage["key"] = "value"
        s.write()

        # Reload
        s2 = Storage.Storage(client)
        s2.read()
        assert s2.storage["key"] == "value"


def test_conf_save_load(mock_env):
    env, s_file, db_file = mock_env
    client = MagicMock()

    with patch("Golconda.Storage.WikiPage"):
        s = Storage.Storage(client)
        s.save_conf("user1", "opt", "val")
        val = s.load_conf("user1", "opt")
        assert val == "val"

        s.save_conf("user1", "opt", "val2")  # Update
        val = s.load_conf("user1", "opt")
        assert val == "val2"
