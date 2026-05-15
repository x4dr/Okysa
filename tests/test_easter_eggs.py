import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import discord
from Golconda import EasterEggs


@pytest.fixture
def mock_bot_user():
    user = MagicMock(spec=discord.User)
    user.name = "BotName"
    user.id = "999"
    return user


@pytest.mark.asyncio
async def test_eastereggs_praise(mock_message, mock_bot_user, mock_singleton):
    mock_singleton.me.name = "BotName"
    mock_message.content = "good job BotName"
    mock_message.author.bot = False

    with (
        patch("Golconda.EasterEggs.me", return_value=mock_bot_user),
        patch(
            "Golconda.EasterEggs.get_ollama_response", new_callable=AsyncMock
        ) as mock_ollama,
        patch("Golconda.EasterEggs.random", return_value=0.01),
    ):
        await EasterEggs.eastereggs(mock_message)
        mock_message.add_reaction.assert_any_call("😳")
        mock_ollama.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_eastereggs_hate(mock_message, mock_bot_user, mock_singleton):
    mock_singleton.me.name = "BotName"
    mock_message.content = "shut up BotName"
    mock_message.author.bot = False

    with (
        patch("Golconda.EasterEggs.me", return_value=mock_bot_user),
        patch(
            "Golconda.EasterEggs.get_ollama_response", new_callable=AsyncMock
        ) as mock_ollama,
        patch("Golconda.EasterEggs.random", return_value=0.01),
    ):
        await EasterEggs.eastereggs(mock_message)
        mock_message.add_reaction.assert_any_call("🖕")
        mock_message.add_reaction.assert_any_call("😭")
        mock_ollama.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_eastereggs_reference_bot(mock_message, mock_bot_user, mock_singleton):
    mock_singleton.me.name = "BotName"
    mock_singleton.me.id = "999"
    mock_message.content = "hello"
    mock_message.author.bot = False
    mock_message.reply_to_id = "12345"

    mock_ref = MagicMock()
    mock_ref.author = mock_bot_user
    mock_message.channel.fetch_message = AsyncMock(return_value=mock_ref)

    with (
        patch("Golconda.EasterEggs.me", return_value=mock_bot_user),
        patch(
            "Golconda.EasterEggs.get_ollama_response", new_callable=AsyncMock
        ) as mock_ollama,
        patch("Golconda.EasterEggs.random", return_value=0.5),
    ):
        await EasterEggs.eastereggs(mock_message)
        mock_ollama.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_eastereggs_bot_author(mock_message, mock_singleton):
    mock_message.author.bot = True
    await EasterEggs.eastereggs(mock_message)
    mock_message.add_reaction.assert_not_called()
