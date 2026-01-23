import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os
from Golconda import Storage
from gamepack.Dice import DescriptiveError


@pytest.fixture
def mock_client_storage():
    client = MagicMock()
    client.user = MagicMock()
    client.application = MagicMock()
    return client


def test_storage_init_misconfigured_wiki(mock_client_storage):
    with (
        patch.dict(
            os.environ,
            {"NOSSI": "link", "DATABASE": "db", "WIKI": "", "STORAGE": "store"},
        ),
        patch("Golconda.Storage.Storage.connect_db"),
        patch("Golconda.Storage.Storage.load_conf", return_value="0"),
    ):
        with pytest.raises(Exception, match="WIKI="):
            Storage.Storage(mock_client_storage)


def test_storage_init_misconfigured_storage(mock_client_storage):
    with (
        patch.dict(
            os.environ,
            {"NOSSI": "link", "DATABASE": "db", "WIKI": "~/wiki", "STORAGE": ""},
        ),
        patch("Golconda.Storage.Storage.connect_db"),
        patch("gamepack.WikiPage.WikiPage.set_wikipath"),
        patch("Golconda.Storage.Storage.load_conf", return_value="0"),
    ):
        with pytest.raises(Exception, match="STORAGE="):
            Storage.Storage(mock_client_storage)


def test_getroles(mock_client_storage):
    with (
        patch.dict(
            os.environ,
            {"NOSSI": "link", "DATABASE": "db", "WIKI": "~/wiki", "STORAGE": "store"},
        ),
        patch("Golconda.Storage.Storage.connect_db"),
        patch("gamepack.WikiPage.WikiPage.set_wikipath"),
        patch("Golconda.Storage.Storage.read"),
        patch("Golconda.Storage.Storage.load_conf", return_value="0"),
    ):
        s = Storage.Storage(mock_client_storage)
        mock_guild = MagicMock()
        mock_guild.me.roles = ["role1"]
        mock_client_storage.get_guild.return_value = mock_guild

        assert s.getroles(123) == ["role1"]

        mock_client_storage.get_guild.return_value = None
        assert s.getroles(456) == []


def test_connect_db_failure(mock_client_storage):
    with (
        patch.dict(
            os.environ,
            {
                "NOSSI": "link",
                "DATABASE": "/invalid/path",
                "WIKI": "~/wiki",
                "STORAGE": "store",
            },
        ),
        patch("gamepack.WikiPage.WikiPage.set_wikipath"),
        patch("Golconda.Storage.Storage.read"),
        patch("Golconda.Storage.Storage.load_conf", return_value="0"),
    ):
        # connect_db is called in __init__
        with pytest.raises(Exception, match="db in env misconfigured"):
            Storage.Storage(mock_client_storage)


@pytest.mark.asyncio
async def test_storage_create(mock_client_storage):
    with (
        patch.dict(
            os.environ,
            {"NOSSI": "link", "DATABASE": "db", "WIKI": "~/wiki", "STORAGE": "store"},
        ),
        patch("Golconda.Storage.Storage.connect_db"),
        patch("gamepack.WikiPage.WikiPage.set_wikipath"),
        patch("Golconda.Storage.Storage.read"),
        patch("Golconda.Storage.Storage.load_conf", return_value="0"),
    ):
        s = await Storage.Storage.create(mock_client_storage)
        assert s.app == mock_client_storage.application


def test_read_nonexistent(mock_client_storage, tmp_path):
    store_path = tmp_path / "nonexistent.json"
    with (
        patch.dict(
            os.environ,
            {
                "NOSSI": "link",
                "DATABASE": "db",
                "WIKI": "~/wiki",
                "STORAGE": str(store_path),
            },
        ),
        patch("Golconda.Storage.Storage.connect_db"),
        patch("gamepack.WikiPage.WikiPage.set_wikipath"),
        patch("Golconda.Storage.Storage.load_conf", return_value="0"),
    ):
        s = Storage.Storage(mock_client_storage)
        assert s.storage == {}


def test_load_entire_conf(mock_client_storage):
    with (
        patch.dict(
            os.environ,
            {"NOSSI": "link", "DATABASE": "db", "WIKI": "~/wiki", "STORAGE": "store"},
        ),
        patch("Golconda.Storage.Storage.connect_db") as mock_conn,
        patch("gamepack.WikiPage.WikiPage.set_wikipath"),
        patch("Golconda.Storage.Storage.read"),
        patch("Golconda.Storage.Storage.load_conf", return_value="0"),
    ):
        s = Storage.Storage(mock_client_storage)
        mock_db = MagicMock()
        mock_conn.return_value = mock_db
        s.db = mock_db

        mock_db.execute.return_value.fetchall.return_value = [
            ("opt1", "val1"),
            ("opt2", "val2"),
        ]
        assert s.load_entire_conf("user") == {"opt1": "val1", "opt2": "val2"}


def test_evilsingleton_raises():
    with patch("Golconda.Storage._Storage", None):
        with pytest.raises(DescriptiveError, match="not initialized yet"):
            Storage.evilsingleton()


@pytest.mark.asyncio
async def test_migrate(mock_client_storage):
    mock_s = MagicMock()
    mock_s.storage = {"user_name#1234": {"defines": {"a": "b"}}}
    with patch("Golconda.Storage._Storage", mock_s):
        user = MagicMock()
        user.__str__ = MagicMock(return_value="user_name#1234")
        user.id = 123456

        mock_client_storage.application.owner.send = AsyncMock()
        await Storage.migrate(mock_client_storage, user)
        assert "123456" in mock_s.storage
        assert "user_name#1234" not in mock_s.storage
        mock_s.write.assert_called()
