import pytest
from unittest.mock import MagicMock, patch
from Commands import Char
from gamepack.FenCharacter import FenCharacter
from gamepack.WikiCharacterSheet import WikiCharacterSheet
from collections import OrderedDict


@pytest.fixture
def mock_chara():
    mock_c = MagicMock(spec=FenCharacter)
    mock_c.Character = {"Name": "Test Char", "Age": "100"}
    mock_c.Categories = OrderedDict(
        {"Stats": OrderedDict({"Physical": OrderedDict({"Str": "5"})})}
    )
    mock_c.Notes = MagicMock()
    mock_c.Notes.originalMD = "Notes content"
    mock_c.experience_headings = ["experience"]
    mock_c.Meta = {
        "experience": MagicMock(tables=[MagicMock(rows=[["Skill", "Cost", "5"]])])
    }
    mock_c.xp_cache = {"Skill": 5}
    return mock_c


def test_maxdots():
    assert Char.maxdots("2", 5) == "●●○○○"
    assert Char.maxdots("invalid", 5) == "invalid"


def test_sectionformat():
    section = OrderedDict({"Str": "5", "Dex": "3"})
    res = Char.sectionformat(section, 5)
    assert "**Str**:\t●●●●●" in res
    assert "**Dex**:\t●●●○○" in res


@pytest.mark.asyncio
async def test_sheet_make_from_success(mock_singleton, mock_chara):
    mock_wiki = MagicMock(spec=WikiCharacterSheet)
    mock_wiki.char = mock_chara

    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch(
            "gamepack.WikiCharacterSheet.WikiCharacterSheet.load_locate",
            return_value=mock_wiki,
        ),
    ):
        mock_singleton.load_conf.return_value = "sheet_id"
        view = Char.Sheet().make_from("sheet_id", [])
        assert view.embed.title == "Test Char"
        assert len(view.children) > 0


@pytest.mark.asyncio
async def test_nav_callback(mock_interaction, mock_singleton, mock_chara):
    mock_interaction.data = {"custom_id": "charsheet:categories"}
    mock_interaction.message.embeds = [MagicMock(url="http://nossi.net/sheet/id")]

    mock_wiki = MagicMock(spec=WikiCharacterSheet)
    mock_wiki.char = mock_chara

    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch(
            "gamepack.WikiCharacterSheet.WikiCharacterSheet.load_locate",
            return_value=mock_wiki,
        ),
    ):
        await Char.nav_callback(mock_interaction)
        mock_interaction.message.edit.assert_called()
        mock_interaction.response.defer.assert_called()


@pytest.mark.asyncio
async def test_xp_command_success(mock_interaction, mock_singleton, mock_chara):
    mock_wiki = MagicMock(spec=WikiCharacterSheet)
    mock_wiki.char = mock_chara
    mock_chara.get_xp_for.return_value = 5
    mock_chara.add_xp.return_value = 10

    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Golconda.CharacterService.who_am_i", return_value="nossi_user"),
        patch(
            "gamepack.WikiCharacterSheet.WikiCharacterSheet.load_locate",
            return_value=mock_wiki,
        ),
    ):
        mock_singleton.storage = {
            str(mock_interaction.user.id): {
                "NossiAccount": "nossi_user",
                "DiscordAccount": str(mock_interaction.user.id),
            }
        }
        mock_singleton.load_conf.return_value = str(mock_interaction.user.id)

        mock_tree = MagicMock()
        # Mock the decorator
        decorator = MagicMock()
        mock_tree.command.return_value = decorator

        Char.register(mock_tree)

        # Find the xp command. It's one of the calls to decorator.
        # calls to mock_tree.command(name="char") -> returns decorator -> decorator(test)
        # calls to mock_tree.command(name="xp") -> returns decorator -> decorator(xp)

        xp_cmd = None
        for call in mock_tree.command.call_args_list:
            if call[1].get("name") == "xp":
                # This call returned a decorator, let's find what that decorator was called with
                # We need to find the call to the *returned* mock
                pass

        # Simpler: just find the call to the decorator that looks like the xp function
        for call in decorator.call_args_list:
            func = call[0][0]
            if func.__name__ == "xp":
                xp_cmd = func
                break

        assert xp_cmd is not None
        await xp_cmd(mock_interaction, skill="Skill", amount=5)
        mock_chara.add_xp.assert_called_with("Skill", 5)
        mock_wiki.save.assert_called()
        mock_interaction.response.send_message.assert_called_with(
            "XP for Skill increased from 5 to 10."
        )
