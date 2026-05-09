import pytest
from unittest.mock import MagicMock, patch
import discord
from Commands import Minecraft


@pytest.fixture
def mock_tree():
    return MagicMock(spec=discord.app_commands.CommandTree)


def test_register_minecraft(mock_tree):
    Minecraft.register(mock_tree)
    mock_tree.add_command.assert_called_once()


@pytest.mark.asyncio
async def test_mcup_allowed(mock_interaction, mock_singleton):
    mock_interaction.user.id = 123
    mock_singleton.storage = {"mc_powerusers": [123]}

    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("subprocess.call") as mock_call,
    ):
        # We need to find the command in the group
        mock_tree = MagicMock()
        Minecraft.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        mcup_cmd = next(c for c in group.commands if c.name == "up")

        await mcup_cmd.callback(mock_interaction)
        mock_interaction.response.send_message.assert_called_with("Starting Server...")
        mock_call.assert_called_with(["mcstart"])


@pytest.mark.asyncio
async def test_mcup_denied(mock_interaction, mock_singleton):
    mock_interaction.user.id = 456
    mock_singleton.storage = {"mc_powerusers": [123]}

    with patch("Golconda.Storage.evilsingleton", return_value=mock_singleton):
        mock_tree = MagicMock()
        Minecraft.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        mcup_cmd = next(c for c in group.commands if c.name == "up")

        await mcup_cmd.callback(mock_interaction)
        mock_interaction.response.send_message.assert_called_with(
            "Access Denied!", ephemeral=True
        )


@pytest.mark.asyncio
async def test_register_user_owner(mock_interaction, mock_singleton, mock_user):
    mock_interaction.guild.owner = mock_interaction.user
    mock_singleton.storage = {"mc_powerusers": []}
    mock_user.id = 789

    with patch("Golconda.Storage.evilsingleton", return_value=mock_singleton):
        mock_tree = MagicMock()
        Minecraft.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        reg_cmd = next(c for c in group.commands if c.name == "reg")

        # Add user
        await reg_cmd.callback(mock_interaction, mock_user)
        assert 789 in mock_singleton.storage["mc_powerusers"]
        mock_interaction.response.send_message.assert_called_with(
            f"Added {mock_user} to allowed users.", ephemeral=False
        )

        # Remove user
        await reg_cmd.callback(mock_interaction, mock_user)
        assert 789 not in mock_singleton.storage["mc_powerusers"]
        mock_interaction.response.send_message.assert_called_with(
            f"Removed {mock_user} from allowed users.", ephemeral=False
        )


@pytest.mark.asyncio
async def test_register_user_denied(mock_interaction, mock_singleton, mock_user):
    mock_interaction.guild.owner = MagicMock()  # someone else

    with patch("Golconda.Storage.evilsingleton", return_value=mock_singleton):
        mock_tree = MagicMock()
        Minecraft.register(mock_tree)
        group = mock_tree.add_command.call_args[0][0]
        reg_cmd = next(c for c in group.commands if c.name == "reg")

        await reg_cmd.callback(mock_interaction, mock_user)
        mock_interaction.response.send_message.assert_called_with(
            "Access Denied!", ephemeral=True
        )
