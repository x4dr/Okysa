import pytest
from unittest.mock import MagicMock, patch
from gamepack.Dice import DescriptiveError
from gamepack.FenCharacter import FenCharacter
from gamepack.WikiCharacterSheet import WikiCharacterSheet
from Golconda import CharacterService


@pytest.fixture
def mock_wiki_sheet():
    mock_wiki = MagicMock(spec=WikiCharacterSheet)
    mock_char = MagicMock(spec=FenCharacter)
    mock_wiki.char = mock_char
    return mock_wiki


def test_load_user_char_stats(mock_singleton, mock_wiki_sheet):
    with (
        patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton),
        patch(
            "gamepack.WikiCharacterSheet.WikiCharacterSheet.load_locate",
            return_value=mock_wiki_sheet,
        ),
    ):
        mock_singleton.load_conf.return_value = "sheet_path"
        mock_wiki_sheet.char.stat_definitions.return_value = {"str": 5}

        stats = CharacterService.load_user_char_stats("nossi_user")
        assert stats == {"str": 5}


def test_load_user_char_not_found(mock_singleton):
    with patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton):
        mock_singleton.load_conf.return_value = None
        assert CharacterService.load_user_char("nossi_user") is None


def test_load_user_char_error(mock_singleton):
    with (
        patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton),
        patch(
            "gamepack.WikiCharacterSheet.WikiCharacterSheet.load_locate",
            side_effect=Exception("Load failed"),
        ),
    ):
        mock_singleton.load_conf.return_value = "sheet_path"
        assert CharacterService.load_user_char("nossi_user") is None


def test_who_am_i_no_account():
    assert CharacterService.who_am_i({}) is None


def test_who_am_i_no_discord_account(mock_singleton):
    with patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton):
        mock_singleton.load_conf.return_value = "confirmed_id"
        with pytest.raises(DescriptiveError, match="I have forgotten who you are"):
            CharacterService.who_am_i({"NossiAccount": "User"})


def test_who_am_i_not_confirmed(mock_singleton):
    with patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton):
        mock_singleton.load_conf.return_value = "other_discord_id(name)"
        with pytest.raises(
            DescriptiveError, match="has not confirmed this discord account"
        ):
            CharacterService.who_am_i(
                {"NossiAccount": "User", "DiscordAccount": "my_id"}
            )


def test_get_discord_user_char_success(mock_singleton, mock_user, mock_wiki_sheet):
    with (
        patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton),
        patch("Golconda.CharacterService.who_am_i", return_value="nossi_user"),
        patch(
            "gamepack.WikiCharacterSheet.WikiCharacterSheet.load_locate",
            return_value=mock_wiki_sheet,
        ),
    ):
        mock_singleton.storage = {str(mock_user.id): {"NossiAccount": "nossi_user"}}
        mock_singleton.load_conf.return_value = "sheet_path"

        char = CharacterService.get_discord_user_char(mock_user)
        assert char == mock_wiki_sheet.char


def test_get_discord_user_char_not_registered(mock_singleton, mock_user):
    with patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton):
        mock_singleton.storage = {}
        with pytest.raises(DescriptiveError, match="You are not registered"):
            CharacterService.get_discord_user_char(mock_user)


def test_get_discord_user_char_no_sheet(mock_singleton, mock_user):
    with (
        patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton),
        patch("Golconda.CharacterService.who_am_i", return_value="nossi_user"),
    ):
        mock_singleton.storage = {str(mock_user.id): {"NossiAccount": "nossi_user"}}
        mock_singleton.load_conf.return_value = None

        with pytest.raises(DescriptiveError, match="No character sheet found"):
            CharacterService.get_discord_user_char(mock_user)


def test_get_discord_user_char_load_fail(mock_singleton, mock_user):
    with (
        patch("Golconda.CharacterService.evilsingleton", return_value=mock_singleton),
        patch("Golconda.CharacterService.who_am_i", return_value="nossi_user"),
        patch(
            "gamepack.WikiCharacterSheet.WikiCharacterSheet.load_locate",
            side_effect=Exception("Load failed"),
        ),
    ):
        mock_singleton.storage = {str(mock_user.id): {"NossiAccount": "nossi_user"}}
        mock_singleton.load_conf.return_value = "sheet_path"

        with pytest.raises(
            DescriptiveError, match="Failed to load your character sheet"
        ):
            CharacterService.get_discord_user_char(mock_user)
