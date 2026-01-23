import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import requests
from Golconda import Ollama


@pytest.fixture
def mock_storage_ollama():
    mock_s = MagicMock()
    mock_s.ollama = "http://ollama:11434"
    return mock_s


def test_get_context_length_success(mock_storage_ollama):
    with (
        patch("Golconda.Ollama.evilsingleton", return_value=mock_storage_ollama),
        patch("requests.post") as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"context_length": 8192}
        mock_post.return_value = mock_response

        Ollama.get_context_length.cache_clear()
        assert Ollama.get_context_length() == 8192


def test_get_context_length_default(mock_storage_ollama):
    with (
        patch("Golconda.Ollama.evilsingleton", return_value=mock_storage_ollama),
        patch("requests.post", side_effect=requests.exceptions.RequestException),
    ):
        Ollama.get_context_length.cache_clear()
        assert Ollama.get_context_length() == 4096


def test_trim_history():
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "how are you?"},
    ]
    # Total length is 5 + 2 + 12 = 19
    trimmed = Ollama.trim_history(history, 15)
    assert len(trimmed) == 2
    assert trimmed[0]["content"] == "hi"


def test_is_ollama_up_success(mock_storage_ollama):
    with (
        patch("Golconda.Ollama.evilsingleton", return_value=mock_storage_ollama),
        patch("requests.get") as mock_get,
    ):
        mock_get.return_value.status_code = 200
        assert Ollama.is_ollama_up() is True


def test_is_ollama_up_fail(mock_storage_ollama):
    with (
        patch("Golconda.Ollama.evilsingleton", return_value=mock_storage_ollama),
        patch("requests.get", side_effect=requests.exceptions.RequestException),
    ):
        assert Ollama.is_ollama_up() is False


@pytest.mark.asyncio
async def test_get_ollama_response_down(mock_storage_ollama, mock_message):
    with (
        patch("Golconda.Ollama.evilsingleton", return_value=mock_storage_ollama),
        patch("Golconda.Ollama.is_ollama_up", return_value=False),
    ):
        await Ollama.get_ollama_response(mock_message)
        mock_message.add_reaction.assert_called_with("💤")


@pytest.mark.asyncio
async def test_get_ollama_response_success(mock_storage_ollama, mock_message):
    with (
        patch("Golconda.Ollama.evilsingleton", return_value=mock_storage_ollama),
        patch("Golconda.Ollama.is_ollama_up", return_value=True),
        patch("Golconda.Ollama.get_context_length", return_value=4096),
        patch("aiohttp.ClientSession.post") as mock_post,
    ):
        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"response": "I am Okysa."}
        mock_resp.__aenter__.return_value = mock_resp
        mock_post.return_value = mock_resp

        await Ollama.get_ollama_response(mock_message)
        mock_message.reply.assert_called_with("I am Okysa.")


@pytest.mark.asyncio
async def test_get_ollama_response_error(mock_storage_ollama, mock_message):
    with (
        patch("Golconda.Ollama.evilsingleton", return_value=mock_storage_ollama),
        patch("Golconda.Ollama.is_ollama_up", return_value=True),
        patch("Golconda.Ollama.get_context_length", return_value=4096),
        patch("aiohttp.ClientSession.post", side_effect=Exception("API Error")),
    ):
        await Ollama.get_ollama_response(mock_message)
        mock_message.add_reaction.assert_called_with("💥")
