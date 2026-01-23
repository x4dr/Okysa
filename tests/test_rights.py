import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from gamepack.Dice import DescriptiveError
from Golconda import Rights


@pytest.fixture
def mock_storage_rights():
    mock_s = MagicMock()
    mock_s.allowed_channels = []
    mock_s.me = MagicMock()
    mock_s.me.name = "BotName"
    mock_s.client = MagicMock()
    mock_s.client.application = MagicMock()
    mock_s.client.application.owner = MagicMock()
    return mock_s


@pytest.mark.asyncio
async def test_allowed_not_initialized():
    with patch(
        "Golconda.Rights.evilsingleton", side_effect=DescriptiveError("Not init")
    ):
        assert await Rights.allowed(MagicMock()) is False


@pytest.mark.asyncio
async def test_allowed_channel(mock_storage_rights, mock_message):
    mock_storage_rights.allowed_channels = [mock_message.channel.id]
    with patch("Golconda.Rights.evilsingleton", return_value=mock_storage_rights):
        assert await Rights.allowed(mock_message) is True


@pytest.mark.asyncio
async def test_allowed_dm(mock_storage_rights, mock_message):
    mock_message.guild = None
    with patch("Golconda.Rights.evilsingleton", return_value=mock_storage_rights):
        assert await Rights.allowed(mock_message) is True


@pytest.mark.asyncio
async def test_allowed_mention(mock_storage_rights, mock_message):
    mock_storage_rights.me = MagicMock()
    mock_message.mentions = [mock_storage_rights.me]
    with patch("Golconda.Rights.evilsingleton", return_value=mock_storage_rights):
        assert await Rights.allowed(mock_message) is True


@pytest.mark.asyncio
async def test_allowed_role_mention(mock_storage_rights, mock_message):
    mock_role = MagicMock()
    mock_role.id = 123
    mock_message.role_mentions = [123]
    mock_storage_rights.getroles.return_value = [mock_role]
    with patch("Golconda.Rights.evilsingleton", return_value=mock_storage_rights):
        assert await Rights.allowed(mock_message) is True


@pytest.mark.asyncio
async def test_allowed_prefix(mock_storage_rights, mock_message):
    mock_storage_rights.me.name = "BotName"
    mock_message.content = "BotName do something"
    with patch("Golconda.Rights.evilsingleton", return_value=mock_storage_rights):
        assert await Rights.allowed(mock_message) is True


def test_is_owner(mock_storage_rights, mock_user):
    mock_storage_rights.client.application.owner = mock_user
    with patch("Golconda.Rights.evilsingleton", return_value=mock_storage_rights):
        Rights.storage()  # set global s
        assert Rights.is_owner(mock_user) is True
        assert Rights.is_owner(MagicMock()) is False


@pytest.mark.asyncio
async def test_owner_only_decorator(mock_storage_rights, mock_user):
    mock_storage_rights.client.application.owner = mock_user

    mock_func = AsyncMock(return_value="success")
    decorated = Rights.owner_only(mock_func)

    with patch("Golconda.Rights.evilsingleton", return_value=mock_storage_rights):
        Rights.storage()
        # Call as owner
        res = await decorated(mock_user, arg1="val1")
        assert res == "success"
        mock_func.assert_called_once_with(mock_user, arg1="val1", user=mock_user.id)

        # Call as non-owner
        mock_func.reset_mock()
        non_owner = MagicMock()
        res = await decorated(non_owner)
        assert res is None
        mock_func.assert_not_called()
