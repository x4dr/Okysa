import pytest
import unittest.mock
from unittest.mock import AsyncMock
from Golconda import Routing


@pytest.mark.asyncio
async def test_main_route_invoke(mock_message, mock_singleton):
    mock_message.content = "invoke"
    with unittest.mock.patch(
        "Golconda.Routing.invoke", new_callable=AsyncMock
    ) as mock_inv:
        await Routing.main_route(mock_message)
        mock_inv.assert_called_with(mock_message)


@pytest.mark.asyncio
async def test_main_route_banish(mock_message, mock_singleton):
    mock_message.content = "banish"
    with unittest.mock.patch(
        "Golconda.Routing.banish", new_callable=AsyncMock
    ) as mock_ban:
        await Routing.main_route(mock_message)
        mock_ban.assert_called_with(mock_message)


@pytest.mark.asyncio
async def test_main_route_roll(mock_message, mock_singleton):
    mock_message.content = "1d20"
    with unittest.mock.patch(
        "Golconda.Routing.rollhandle", new_callable=AsyncMock
    ) as mock_rh, unittest.mock.patch("Golconda.Routing.get_remembering_send"):

        mock_rh.return_value = "Result"
        await Routing.main_route(mock_message)
        mock_rh.assert_called()
