import pytest
from unittest.mock import MagicMock, patch
from Commands import Wiki
from gamepack.MDPack import MDObj


def test_table_render():
    # Setup a mock MDObj with tables
    node = MagicMock(spec=MDObj)
    table_mock = MagicMock()
    table_mock.headers = ["H1", "Header 2"]
    table_mock.rows = [["c1", "content 2"], ["val1", "v2"]]
    node.tables = [table_mock]

    result = Wiki.table_render(node)
    assert "H1" in result
    assert "Header 2" in result
    assert "c1" in result


@pytest.mark.asyncio
async def test_make_from():
    with patch("Commands.Wiki.WikiPage") as mock_wp, patch(
        "Commands.Wiki.evilsingleton"
    ) as mock_evil:

        mock_evil.return_value.nossilink = "nossinet.cc"

        mock_page = MagicMock()
        mock_wp.load_locate.return_value = mock_page

        mock_md = MagicMock()
        mock_md.plaintext = "Content"
        mock_md.children = {
            "sub": MagicMock(children={})
        }  # recursive structure needed or just next step
        mock_md.tables = []
        mock_page.md.return_value = mock_md
        mock_page.tags = ["tag1"]

        # Call make_from
        view = Wiki.Wiki.make_from("page:sub")

        assert isinstance(view, Wiki.Wiki)
        assert view.embed.title == "page->sub"
        assert view.embed.url.startswith("https://nossinet.cc/wiki/")
