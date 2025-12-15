import pytest
from unittest.mock import AsyncMock, patch
from Commands import Base


def test_message_prep():
    with patch("Commands.Base.evilsingleton") as mock_evil:
        mock_evil.return_value.me.name = "BotName"

        # Test 1: plain message
        gen = Base.message_prep("Hello World")
        # yielded: ['Hello', 'World']
        res = list(gen)
        assert res[0] == ["Hello", "World"]

        # Test 2: self name strip
        gen = Base.message_prep("BotName do this")
        res = list(gen)
        # Should strip BotName
        assert res[0] == ["do", "this"]


@pytest.mark.asyncio
async def test_invoke(mock_message):
    with patch("Commands.Base.evilsingleton") as mock_evil:
        mock_evil.return_value.allowed_channels = []

        await Base.invoke(mock_message)

        assert mock_message.channel.id in mock_evil.return_value.allowed_channels
        mock_message.reply.assert_called()


@pytest.mark.asyncio
async def test_banish(mock_message):
    with patch("Commands.Base.evilsingleton") as mock_evil:
        mock_evil.return_value.allowed_channels = [mock_message.channel.id]

        await Base.banish(mock_message)

        assert mock_message.channel.id not in mock_evil.return_value.allowed_channels
        mock_message.add_reaction.assert_called()


@pytest.mark.asyncio
async def test_make_bridge(mock_message, mock_singleton):
    with patch("Golconda.Rights.is_owner", return_value=True), patch(
        "Commands.Base.evilsingleton", return_value=mock_singleton
    ):

        mock_message.channel.create_webhook = AsyncMock()
        mock_message.channel.create_webhook.return_value.url = "http://webhook"

        res = await Base.make_bridge(mock_message)
        assert res is True
        assert mock_singleton.bridge_channel == mock_message.channel.id
