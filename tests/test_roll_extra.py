import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from Commands import Roll


@pytest.fixture
def mock_tree():
    return MagicMock()


def test_register_roll(mock_tree):
    Roll.register(mock_tree)
    # Check if commands were added
    assert mock_tree.command.called


@pytest.mark.asyncio
async def test_doroll_success(mock_interaction, mock_singleton):
    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Commands.Roll.rollhandle", new_callable=AsyncMock) as mock_rh,
    ):
        mock_tree = MagicMock()
        decorator = MagicMock()
        mock_tree.command.return_value = decorator
        Roll.register(mock_tree)

        doroll_cmd = next(
            call[0][0]
            for call in decorator.call_args_list
            if call[0][0].__name__ == "doroll"
        )

        await doroll_cmd(mock_interaction, roll="1d20")
        mock_interaction.response.send_message.assert_called()
        mock_rh.assert_called()


@pytest.mark.asyncio
async def test_callroll_command(mock_interaction):
    mock_tree = MagicMock()
    decorator = MagicMock()
    mock_tree.command.return_value = decorator
    Roll.register(mock_tree)

    callroll_cmd = next(
        call[0][0]
        for call in decorator.call_args_list
        if call[0][0].__name__ == "callroll"
    )

    await callroll_cmd(mock_interaction, text="Roll now", rolls="1d20")
    mock_interaction.response.send_message.assert_called()
    _, kwargs = mock_interaction.response.send_message.call_args
    assert "embed" in kwargs
    assert "view" in kwargs


@pytest.mark.asyncio
async def test_rollcall_reveal(mock_interaction):
    view = Roll.RollCall(text="Roll", options="1d20", author=mock_interaction.user)
    view.rolls = [[False, mock_interaction.user, MagicMock(), ["output"], ["reaction"]]]

    mock_interaction.client.application.owner = mock_interaction.user

    await view.reveal(mock_interaction)
    assert view.rolls[0][0] is True
    mock_interaction.channel.send.assert_called()


@pytest.mark.asyncio
async def test_rollcall_add_roll(mock_interaction, mock_singleton):
    view = Roll.RollCall(text="Roll", options="1d20", author=mock_interaction.user)
    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Golconda.RollInterface.rollhandle", new_callable=AsyncMock) as mock_rh,
    ):
        mock_rh.return_value = MagicMock()
        await view.add_roll(mock_interaction.user, "1d20")
        assert len(view.rolls) == 1
