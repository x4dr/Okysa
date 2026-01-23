import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from Commands import Wiki
from gamepack.Dice import DescriptiveError
from gamepack.WikiPage import WikiPage
from gamepack.MDPack import MDObj


@pytest.fixture
def mock_wiki_page():
    mock_page = MagicMock(spec=WikiPage)
    mock_md = MagicMock(spec=MDObj)
    mock_md.plaintext = "TOC content"
    mock_md.children = {}
    mock_md.tables = []
    mock_page.md.return_value = mock_md
    mock_page.tags = ["tag1"]
    mock_page.title = "Page Title"
    return mock_page


def test_dict_search():
    tree = {"a": {"b": 1}, "c": [{"d": 2}]}
    results = list(Wiki.dict_search("b", tree))
    assert ("a", "b") in results

    results = list(Wiki.dict_search("d", tree))
    assert ("c", 0, "d") in results


def test_table_render():
    mock_node = MagicMock(spec=MDObj)
    mock_table = MagicMock()
    mock_table.headers = ["H1", "H2"]
    mock_table.rows = [["R1C1", "R1C2"]]
    mock_node.tables = [mock_table]

    res = Wiki.table_render(mock_node)
    assert "H1" in res
    assert "R1C1" in res


@pytest.mark.asyncio
async def test_wiki_make_from_success(mock_singleton, mock_wiki_page):
    mock_sub_md = MagicMock(spec=MDObj)
    mock_sub_md.plaintext = "Sub content"
    mock_sub_md.children = {}
    mock_sub_md.tables = []
    mock_wiki_page.md().children = {"path": mock_sub_md}

    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Commands.Wiki.WikiPage.load_locate", return_value=mock_wiki_page),
    ):
        mock_singleton.nossilink = "nossi.net"
        view = Wiki.Wiki.make_from("site:path")
        assert view.embed is not None
        assert view.embed.title == "site->path"


@pytest.mark.asyncio
async def test_wiki_make_from_invalid_step(mock_singleton, mock_wiki_page):
    mock_wiki_page.md().children = {"valid": MagicMock()}
    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Commands.Wiki.WikiPage.load_locate", return_value=mock_wiki_page),
    ):
        with pytest.raises(DescriptiveError, match="invalid step in path"):
            Wiki.Wiki.make_from("site:invalid")


@pytest.mark.asyncio
async def test_edit_modal_submit_success(
    mock_interaction, mock_singleton, mock_wiki_page
):
    mock_wiki_page.md().get_content_by_path.return_value = MagicMock()
    mock_sub_md = MagicMock(spec=MDObj)
    mock_sub_md.plaintext = "Sub content"
    mock_sub_md.children = {}
    mock_sub_md.tables = []
    mock_wiki_page.md().children = {"path": mock_sub_md}
    mock_interaction.response.is_done.return_value = False

    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Commands.Wiki.WikiPage.load_locate", return_value=mock_wiki_page),
        patch("Commands.Wiki.WikiPage.locate", return_value=Path("proper_path")),
        patch("Commands.Wiki.WikiPage.load", return_value=mock_wiki_page),
        patch("Commands.Wiki.WikiPage.reload_cache"),
        patch("Commands.Wiki.who_am_i", return_value="nossi_user"),
    ):
        mock_singleton.storage = {
            str(mock_interaction.user.id): {"NossiAccount": "nossi_user"}
        }

        modal = Wiki.EditModal("site:path")
        modal.text_input = MagicMock()
        modal.text_input.value = "new text"

        await modal.on_submit(mock_interaction)
        mock_wiki_page.save.assert_called()
        mock_interaction.response.defer.assert_called()


@pytest.mark.asyncio
async def test_nav_callback(mock_interaction, mock_singleton, mock_wiki_page):
    mock_interaction.data = {"custom_id": "wiki:site:path"}
    mock_sub_md = MagicMock(spec=MDObj)
    mock_sub_md.plaintext = "Sub content"
    mock_sub_md.children = {}
    mock_sub_md.tables = []
    mock_wiki_page.md().children = {"path": mock_sub_md}

    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Commands.Wiki.WikiPage.load_locate", return_value=mock_wiki_page),
    ):
        await Wiki.nav_callback(mock_interaction)
        mock_interaction.message.edit.assert_called()
        mock_interaction.response.defer.assert_called()


@pytest.mark.asyncio
async def test_wiki_command(mock_interaction, mock_singleton, mock_wiki_page):
    with (
        patch("Golconda.Storage.evilsingleton", return_value=mock_singleton),
        patch("Commands.Wiki.WikiPage.load_locate", return_value=mock_wiki_page),
    ):
        mock_tree = MagicMock()
        # Mock the decorator
        decorator = MagicMock()
        mock_tree.command.return_value = decorator

        Wiki.register(mock_tree)

        # The last call to decorator is our function
        wiki_cmd = decorator.call_args[0][0]

        await wiki_cmd(mock_interaction, site="site", path="path")
        mock_interaction.response.send_message.assert_called()
