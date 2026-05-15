from unittest.mock import MagicMock, patch, AsyncMock
import discord
import pytest
from Frontends.DiscordFrontend import DiscordBot


@pytest.fixture
def mock_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = DiscordBot(intents=intents)
    with (
        patch.object(discord.Client, "user", new_callable=MagicMock) as mock_user,
        patch.object(discord.Client, "application", new_callable=MagicMock) as mock_app,
    ):
        mock_user.id = 999
        mock_user.name = "Okysa"
        mock_app.owner = AsyncMock()
        yield bot


@pytest.mark.asyncio
async def test_on_ready(mock_bot):
    with (
        patch("Frontends.DiscordFrontend.setup", new_callable=AsyncMock) as mock_setup,
        patch(
            "Frontends.DiscordFrontend.clockhandle", new_callable=AsyncMock
        ) as mock_clock,
        patch(
            "Frontends.DiscordFrontend.periodic", new_callable=AsyncMock
        ) as mock_periodic,
        patch.object(
            DiscordBot, "change_presence", new_callable=AsyncMock
        ) as mock_presence,
    ):
        await mock_bot.on_ready()
        mock_setup.assert_called_once()
        mock_clock.assert_called_once()
        mock_periodic.assert_called_once()
        mock_presence.assert_called_once()


@pytest.mark.asyncio
async def test_on_message_bridge(mock_bot, mock_message, mock_singleton):
    mock_message.channel.id = 123
    mock_singleton.bridge_channel = 123

    with (patch("Frontends.DiscordFrontend.migrate", new_callable=AsyncMock),):
        await mock_bot.on_message(mock_message)
        mock_singleton.store_message.assert_called_with(mock_message)


@pytest.mark.asyncio
async def test_on_message_allowed(mock_bot, mock_message, mock_singleton):
    mock_message.channel.id = 456
    mock_singleton.bridge_channel = 123
    mock_singleton.allowed_channels = ["456"]

    with (
        patch(
            "Frontends.DiscordFrontend.main_route", new_callable=AsyncMock
        ) as mock_route,
        patch(
            "Frontends.DiscordFrontend.migrate", new_callable=AsyncMock
        ) as mock_migrate,
    ):
        await mock_bot.on_message(mock_message)
        mock_route.assert_called_once()
        mock_migrate.assert_called()


@pytest.mark.asyncio
async def test_on_raw_message_edit(mock_bot, mock_message, mock_singleton):
    event = MagicMock(spec=discord.RawMessageUpdateEvent)
    event.channel_id = 123
    event.message_id = 456

    with (
        patch.object(DiscordBot, "get_channel") as mock_get_channel,
        patch("Frontends.DiscordFrontend.allowed", return_value=True),
        patch(
            "Frontends.DiscordFrontend.main_route", new_callable=AsyncMock
        ) as mock_route,
    ):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.fetch_message.return_value = mock_message
        mock_get_channel.return_value = mock_channel
        mock_message.author = MagicMock(spec=discord.Member)
        mock_message.author.id = 111

        await mock_bot.on_raw_message_edit(event)
        mock_route.assert_called_once()
