import pytest
from Commands import Char


@pytest.mark.asyncio
async def test_sheet_initialization():
    view = Char.Sheet()
    assert view.sheetlink == "https://nossinet.cc/sheet/"
    assert view.prefix == "charsheet:"


@pytest.mark.asyncio
async def test_sheet_interaction(mock_interaction):
    view = Char.Sheet()
    assert view is not None
