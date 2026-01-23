import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import discord
from Commands import Oracle


@pytest.fixture
def mock_tree():
    return MagicMock(spec=discord.app_commands.CommandTree)


def test_register_oracle(mock_tree):
    Oracle.register(mock_tree)
    mock_tree.add_command.assert_called_once()


@pytest.mark.asyncio
async def test_versus_success(mock_interaction):
    with patch("Commands.Oracle.versus", return_value=("work", 10.0, 2.0)):
        mock_tree = MagicMock()
        Oracle.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        v_cmd = next(c for c in group.commands if c.name == "versus")

        await v_cmd.callback(
            mock_interaction,
            selector1="1 2",
            selector2="3 4",
            advantage1=1,
            advantage2=0,
            mode=0,
        )
        mock_interaction.response.send_message.assert_called()
        args = mock_interaction.response.send_message.call_args[0][0]
        assert "avg: 10.0" in args


@pytest.mark.asyncio
async def test_versus_invalid_selectors(mock_interaction):
    mock_tree = MagicMock()
    Oracle.register(mock_tree)
    group = mock_tree.add_command.call_args[0][0]
    v_cmd = next(c for c in group.commands if c.name == "versus")

    await v_cmd.callback(mock_interaction, selector1="invalid", selector2="10")
    mock_interaction.response.send_message.assert_called_with(
        "error: The given selectors didnt make sense.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_selectors_ascii_success(mock_interaction):
    with patch("Commands.Oracle.chances", return_value=("graph", 5.0, 1.0)):
        mock_tree = MagicMock()
        Oracle.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        sel_cmd = next(c for c in group.commands if c.name == "selectors")

        mode_mock = MagicMock()
        mode_mock.value = 1
        await sel_cmd.callback(
            mock_interaction, selectors="1 2", advantage=1, mode=mode_mock
        )
        mock_interaction.response.send_message.assert_called()
        args = mock_interaction.response.send_message.call_args[0][0]
        assert "avg: 5.0" in args


@pytest.mark.asyncio
async def test_oracle_try(mock_interaction):
    with patch(
        "Commands.Oracle.timeout", new_callable=AsyncMock, return_value="result"
    ):
        mock_tree = MagicMock()
        Oracle.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        try_cmd = next(c for c in group.commands if c.name == "try")

        await try_cmd.callback(mock_interaction, roll="1d20")
        mock_interaction.response.send_message.assert_called_with(
            "Applying the numerical HAMMER for 10 seconds..."
        )
        mock_interaction.edit_original_response.assert_called()


@pytest.mark.asyncio
async def test_oracle_show_success(mock_interaction):
    import io

    with patch("Commands.Oracle.chances", return_value=io.BytesIO(b"fake image data")):
        mock_tree = MagicMock()
        Oracle.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        show_cmd = next(c for c in group.commands if c.name == "showselectors")

        await show_cmd.callback(
            mock_interaction, selectors="1", advantage=0, percentiles=0, mode=None
        )
        mock_interaction.response.send_message.assert_called()
        _, kwargs = mock_interaction.response.send_message.call_args
        assert "file" in kwargs
