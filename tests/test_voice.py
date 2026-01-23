import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from Commands import Voice


@pytest.mark.asyncio
async def test_stream_no_voice(mock_interaction):
    mock_interaction.user.voice = None

    mock_tree = MagicMock()
    decorator = MagicMock()
    mock_tree.command.return_value = decorator
    Voice.register(mock_tree)
    stream_cmd = decorator.call_args[0][0]

    await stream_cmd(mock_interaction)
    mock_interaction.edit_original_response.assert_called_with(
        content="You are not in a voice channel."
    )


@pytest.mark.asyncio
async def test_stream_success(mock_interaction):
    mock_interaction.user.voice = MagicMock()
    mock_channel = AsyncMock()
    mock_interaction.user.voice.channel = mock_channel

    mock_connection = MagicMock()
    mock_connection.is_playing.side_effect = [True, False]
    mock_connection.disconnect = AsyncMock()
    mock_channel.connect.return_value = mock_connection

    with (
        patch("Commands.Voice.soundpipe"),
        patch("asyncio.sleep", return_value=None),
    ):
        mock_tree = MagicMock()
        decorator = MagicMock()
        mock_tree.command.return_value = decorator
        Voice.register(mock_tree)
        stream_cmd = decorator.call_args[0][0]

        await stream_cmd(mock_interaction)
        mock_connection.play.assert_called()
        mock_connection.disconnect.assert_called()
