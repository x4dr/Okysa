import unittest.mock
from unittest.mock import AsyncMock

import pytest

from Golconda import Routing


@pytest.mark.asyncio
async def test_main_route_invoke(mock_message, mock_singleton):
    mention = "<@bot_id>"
    mock_singleton.client.user.mention = mention
    mock_message.content = f"{mention} invoke"
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
    with (
        unittest.mock.patch(
            "Golconda.Routing.rollhandle", new_callable=AsyncMock
        ) as mock_rh,
        unittest.mock.patch("Golconda.Routing.get_remembering_send"),
    ):
        mock_rh.return_value = "Result"
        await Routing.main_route(mock_message)
        mock_rh.assert_called()


@pytest.mark.asyncio
async def test_main_route_def(mock_message, mock_singleton):
    mock_message.content = "def test = value"
    with unittest.mock.patch(
        "Golconda.Routing.define", new_callable=AsyncMock
    ) as mock_def:
        await Routing.main_route(mock_message)
        mock_def.assert_called_once()


@pytest.mark.asyncio
async def test_main_route_undef(mock_message, mock_singleton):
    mock_message.content = "undef test"
    with unittest.mock.patch(
        "Golconda.Routing.undefine", new_callable=AsyncMock
    ) as mock_undef:
        await Routing.main_route(mock_message)
        mock_undef.assert_called_once()


@pytest.mark.asyncio
async def test_main_route_die(mock_message, mock_singleton):
    mock_message.content = "DIE"
    with (
        unittest.mock.patch("Golconda.Routing.is_owner", return_value=True),
        unittest.mock.patch.object(
            mock_singleton.client, "close", new_callable=AsyncMock
        ) as mock_close,
    ):
        await Routing.main_route(mock_message)
        mock_close.assert_called_once()
        mock_message.add_reaction.assert_called_with("\U0001f480")
