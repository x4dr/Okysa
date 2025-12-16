import pytest
from unittest.mock import AsyncMock, Mock

from Commands import Base
from Golconda.Storage import Storage


def test_message_prep():
    # Test 1: plain message
    gen = Base.message_prep("Hello World", "BotName")
    res = list(gen)
    assert res[0] == ["Hello", "World"]

    # Test 2: self name strip
    gen = Base.message_prep("BotName do this", "BotName")
    res = list(gen)
    # Should strip BotName
    assert res[0] == ["do", "this"]


@pytest.mark.asyncio
async def test_invoke(mock_message):
    # Create mock storage
    mock_storage = Mock(spec=Storage)
    mock_storage.allowed_channels = []
    mock_storage.write = Mock()

    # Attach to message.client
    mock_message.client.storage = mock_storage

    await Base.invoke(mock_message)

    assert mock_message.channel.id in mock_storage.allowed_channels
    mock_message.reply.assert_called()


@pytest.mark.asyncio
async def test_banish(mock_message):
    # Create mock storage
    mock_storage = Mock(spec=Storage)
    mock_storage.allowed_channels = [mock_message.channel.id]
    mock_storage.write = Mock()

    # Attach to message.client
    mock_message.client.storage = mock_storage

    await Base.banish(mock_message)

    assert mock_message.channel.id not in mock_storage.allowed_channels
    mock_message.add_reaction.assert_called()


@pytest.mark.asyncio
async def test_make_bridge(mock_message, mock_singleton):
    from unittest.mock import patch

    # Create mock storage
    mock_storage = Mock(spec=Storage)
    mock_storage.bridge_channel = 0
    mock_storage.save_conf = Mock()

    # Attach to message.client
    mock_message.client.storage = mock_storage

    with patch("Golconda.Rights.is_owner", return_value=True):
        mock_message.channel.create_webhook = AsyncMock()
        mock_message.channel.create_webhook.return_value.url = "http://webhook"

        res = await Base.make_bridge(mock_message)
        assert res is True
        assert mock_storage.bridge_channel == mock_message.channel.id
