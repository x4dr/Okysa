import pytest
from unittest.mock import MagicMock, AsyncMock, Mock
import discord
from Golconda.Storage import Storage


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
def mock_client():
    """Mock OkysaBot client with storage"""
    client = MagicMock()
    client.user = MagicMock()
    client.user.name = "TestBot"
    client.user.id = 999999999

    # Create mock storage
    mock_storage = Mock(spec=Storage)
    mock_storage.me = client.user
    mock_storage.storage = {}
    mock_storage.allowed_channels = []
    mock_storage.write = Mock()
    mock_storage.save_conf = Mock()

    client.storage = mock_storage
    return client


@pytest.fixture
def mock_interaction(mock_user, mock_channel, mock_message, mock_client):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = mock_user
    interaction.channel = mock_channel
    interaction.message = mock_message
    interaction.guild_id = 111
    interaction.client = mock_client
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
    """Legacy fixture for backwards compatibility - creates a mock storage"""
    mock_s = Mock(spec=Storage)
    mock_s.me = MagicMock()
    mock_s.me.name = "TestBot"
    mock_s.storage = {}
    mock_s.allowed_channels = []
    mock_s.bridge_channel = 0
    mock_s.save_conf = Mock()
    mock_s.write = Mock()
    return mock_s


@pytest.fixture
def mock_message(mock_user, mock_channel, mock_client):
    message = MagicMock(spec=discord.Message)
    message.author = mock_user
    message.channel = mock_channel
    message.client = mock_client
    message.content = "Test message"
    message.id = 55555
    message.mentions = []
    message.add_reaction = AsyncMock()
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    message.reply = AsyncMock()
    return message
