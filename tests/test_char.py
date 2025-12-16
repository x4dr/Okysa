import pytest
from unittest.mock import MagicMock
from Commands import Char


@pytest.mark.asyncio
async def test_sheet_initialization():
    mock_s = MagicMock()
    mock_s.nossilink = "nossinet.cc"
    view = Char.Sheet(mock_s)
    assert view.prefix == "charsheet:"


@pytest.mark.asyncio
async def test_sheet_interaction(mock_interaction):
    mock_s = MagicMock()
    mock_s.nossilink = "nossinet.cc"
    view = Char.Sheet(mock_s)
    assert view is not None
