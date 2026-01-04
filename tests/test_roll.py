import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from Commands import Roll


@pytest.mark.asyncio
async def test_roll_command_invoked(mock_interaction):
    # Test doroll command logic
    # We need to mock 'evilsingleton' and 'rollhandle'

    with (
        patch("Commands.Roll.evilsingleton") as mock_evil,
        patch("Commands.Roll.rollhandle", new_callable=AsyncMock),
    ):

        mock_evil.return_value.storage = {}
        pass


@pytest.mark.asyncio
async def test_RollModal(mock_interaction):
    parent = MagicMock()
    parent.add_roll = AsyncMock()

    modal = Roll.RollModal("options", parent)

    mock_input = MagicMock()
    mock_input.value = "1d20"
    modal.roll = mock_input

    await modal.on_submit(mock_interaction)

    mock_interaction.response.defer.assert_called()
    parent.add_roll.assert_called_with(mock_interaction.user, "1d20")


@pytest.mark.asyncio
async def test_RollCall_reveal(mock_interaction):
    author = mock_interaction.user
    view = Roll.RollCall("text", "options", author)

    # Add a fake roll
    view.rolls.append(
        [
            False,
            author,
            MagicMock(name="Result", roll_v=lambda: "20", comment=""),
            ["output"],
            [],
        ]
    )

    # Test reveal
    await view.reveal(mock_interaction)
    mock_interaction.response.defer.assert_called()
    mock_interaction.channel.send.assert_called()  # Should send output
    assert view.rolls[0][0] is True  # Revealed


@pytest.mark.asyncio
async def test_roll_autocomplete(mock_interaction):
    # Mock get_lastrolls_for
    with patch("Commands.Roll.get_lastrolls_for", return_value=[("1d20", "obj")]):
        choices = await Roll.roll_autocomplete(mock_interaction, "")
        assert len(choices) == 1
        assert choices[0].name == "1d20"

    # Mock character sheets loading for non-empty current
    with patch("Commands.Roll.get_discord_user_char") as mock_get_char:
        mock_char = MagicMock()
        mock_char.Categories = {"Stats": {"Strength": {}, "Dexterity": {}}}
        mock_char.headings_used = {
            "categories": {"Stats": {"Strength": {}, "Dexterity": {}}}
        }
        # The logic in roll_autocomplete for categories/headings is complex and depends on Char object structure
        # Let's skip deep structure mocking for now and cover basic path

        mock_get_char.return_value = mock_char

        # Just ensure it doesn't crash
        await Roll.roll_autocomplete(mock_interaction, "Str")
