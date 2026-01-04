import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord


@pytest.fixture
def mock_user():
    user = MagicMock(spec=discord.User)
    user.name = "TestUser"
    user.id = 123456789
    user.mention = "<@123456789>"
    user.send = AsyncMock()
    return user


@pytest.fixture
def mock_channel():
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "general"
    channel.id = 987654321
    channel.send = AsyncMock()
    channel.fetch_message = AsyncMock()
    channel.history = MagicMock()
    return channel


@pytest.fixture
def mock_interaction(mock_user, mock_channel, mock_message):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = mock_user
    interaction.channel = mock_channel
    interaction.message = mock_message
    interaction.guild_id = 111
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def mock_singleton():
    with patch("Golconda.Storage._Storage", MagicMock()) as mock_s:
        mock_s.me.name = "TestBot"
        mock_s.me.name = "TestBot"
        mock_s.storage = {}
        mock_s.allowed_channels = []
        yield mock_s


@pytest.fixture
def mock_message(mock_user, mock_channel):
    message = MagicMock(spec=discord.Message)
    message.author = mock_user
    message.channel = mock_channel
    message.content = "Test message"
    message.id = 55555
    message.mentions = []
    message.add_reaction = AsyncMock()
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    message.reply = AsyncMock()
    return message
