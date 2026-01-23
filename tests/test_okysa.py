import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import discord
import Okysa


@pytest.fixture
def mock_client():
    client = MagicMock(spec=discord.Client)
    client.user = MagicMock()
    client.application = MagicMock()
    client.application.owner = MagicMock()
    return client


@pytest.mark.asyncio
async def test_on_ready():
    with (
        patch("Okysa.setup", new_callable=AsyncMock) as mock_setup,
        patch("Okysa.clockhandle", new_callable=AsyncMock) as mock_clock,
        patch("Okysa.periodic", new_callable=AsyncMock) as mock_periodic,
        patch("Okysa.client.change_presence", new_callable=AsyncMock) as mock_presence,
    ):
        # Manually trigger the event handler
        # In Okysa.py, client is a global
        await Okysa.on_ready()

        mock_setup.assert_called_once()
        mock_clock.assert_called_once()
        mock_periodic.assert_called_once()
        mock_presence.assert_called_once()


@pytest.mark.asyncio
async def test_on_message_bridge(mock_message):
    mock_message.channel.id = 123
    mock_singleton = MagicMock()
    mock_singleton.bridge_channel = 123

    with (
        patch("Okysa.evilsingleton", return_value=mock_singleton),
        patch("Okysa.allowed", return_value=False),
        patch("Okysa.migrate", new_callable=AsyncMock),
    ):  # stop migrate error
        await Okysa.on_message(mock_message)
        mock_singleton.store_message.assert_called_with(mock_message)


@pytest.mark.asyncio
async def test_on_message_treesync(mock_message):
    mock_message.channel.id = 456
    mock_message.content = "treesync"
    mock_singleton = MagicMock()
    mock_singleton.bridge_channel = 123

    with (
        patch("Okysa.evilsingleton", return_value=mock_singleton),
        patch("Okysa.allowed", return_value=True),
        patch("Okysa.is_owner", return_value=True),
        patch("Okysa.main_route", new_callable=AsyncMock),
        patch("Okysa.migrate", new_callable=AsyncMock),
        patch("Okysa.tree.sync", new_callable=AsyncMock) as mock_sync,
    ):
        mock_sync.return_value = [MagicMock(name="cmd1")]
        await Okysa.on_message(mock_message)
        mock_message.channel.send.assert_called()


def test_configure_logging():
    with (
        patch("logging.getLogger"),
        patch("logging.handlers.RotatingFileHandler"),
        patch("logging.Formatter"),
        patch("sys.stdout"),
    ):
        Okysa.configure_logging()


@pytest.mark.asyncio
async def test_on_message_not_allowed(mock_message):
    mock_message.channel.id = 456
    mock_message.content = "?test"
    mock_singleton = MagicMock()
    mock_singleton.bridge_channel = 123

    with (
        patch("Okysa.evilsingleton", return_value=mock_singleton),
        patch("Okysa.allowed", return_value=False),
        patch("Okysa.migrate", new_callable=AsyncMock),
    ):
        with patch("logging.error") as mock_log_err:
            await Okysa.on_message(mock_message)
            mock_log_err.assert_called()


@pytest.mark.asyncio
async def test_on_message_allowed(mock_message):
    mock_message.channel.id = 456
    mock_singleton = MagicMock()
    mock_singleton.bridge_channel = 123

    with (
        patch("Okysa.evilsingleton", return_value=mock_singleton),
        patch("Okysa.allowed", return_value=True),
        patch("Okysa.main_route", new_callable=AsyncMock) as mock_route,
        patch("Okysa.migrate", new_callable=AsyncMock) as mock_migrate,
    ):
        mock_message.author = MagicMock(spec=discord.User)
        mock_message.content = "hello"

        await Okysa.on_message(mock_message)
        mock_route.assert_called_with(mock_message)
        mock_migrate.assert_called()


@pytest.mark.asyncio
async def test_on_raw_message_edit(mock_message):
    event = MagicMock(spec=discord.RawMessageUpdateEvent)
    event.channel_id = 123
    event.message_id = 456

    with (
        patch("Okysa.client.get_channel") as mock_get_channel,
        patch("Okysa.allowed", return_value=True),
        patch("Okysa.main_route", new_callable=AsyncMock) as mock_route,
    ):
        mock_channel = AsyncMock()
        mock_channel.fetch_message.return_value = mock_message
        mock_get_channel.return_value = mock_channel
        mock_message.author = MagicMock()

        await Okysa.on_raw_message_edit(event)
        mock_route.assert_called_with(mock_message)


@pytest.mark.asyncio
async def test_on_raw_message_delete():
    event = MagicMock(spec=discord.RawMessageDeleteEvent)
    event.message_id = 456

    with patch("Okysa.client.get_channel") as mock_get_channel:
        mock_channel = MagicMock()
        mock_get_channel.return_value = mock_channel

        mock_message = MagicMock()
        mock_channel.get_partial_message.return_value = mock_message

        # Mock history
        async def mock_history(*args, **kwargs):
            m = MagicMock()
            m.author = Okysa.client.user
            m.reference.message_id = 456
            yield m

        mock_channel.history.side_effect = mock_history

        await Okysa.on_raw_message_delete(event)
        # Should attempt to delete the related message
        # But we need to be careful with the async generator mock
