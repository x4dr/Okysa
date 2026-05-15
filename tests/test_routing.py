import unittest.mock
from unittest.mock import AsyncMock

import pytest

from Golconda import Routing


@pytest.mark.asyncio
async def test_main_route_invoke(mock_context, mock_singleton):
    mock_context.bot_user.mention = "<@999>"
    mock_context.message.content = "<@999> invoke"
    with unittest.mock.patch(
        "Golconda.Routing.invoke", new_callable=AsyncMock
    ) as mock_inv:
        await Routing.main_route(mock_context)
        mock_inv.assert_called_with(mock_context.message)


@pytest.mark.asyncio
async def test_main_route_banish(mock_context, mock_singleton):
    mock_context.message.content = "banish"
    with unittest.mock.patch(
        "Commands.Base.banish", new_callable=AsyncMock
    ) as mock_ban:
        await Routing.main_route(mock_context)
        mock_ban.assert_called_with(mock_context.message)


@pytest.mark.asyncio
async def test_main_route_roll(mock_context, mock_singleton):
    mock_context.message.content = "1d20"
    with (
        unittest.mock.patch(
            "Golconda.Routing.rollhandle", new_callable=AsyncMock
        ) as mock_rh,
        unittest.mock.patch("Golconda.Routing.get_remembering_send"),
    ):
        mock_rh.return_value = "Result"
        await Routing.main_route(mock_context)
        mock_rh.assert_called()


@pytest.mark.asyncio
async def test_main_route_def(mock_context, mock_singleton):
    mock_context.message.content = "def test = value"
    with unittest.mock.patch(
        "Golconda.Tools.define", new_callable=AsyncMock
    ) as mock_def:
        await Routing.main_route(mock_context)
        mock_def.assert_called_once()


@pytest.mark.asyncio
async def test_main_route_undef(mock_context, mock_singleton):
    mock_context.message.content = "undef test"
    with unittest.mock.patch(
        "Golconda.Tools.undefine", new_callable=AsyncMock
    ) as mock_undef:
        await Routing.main_route(mock_context)
        mock_undef.assert_called_once()


@pytest.mark.asyncio
async def test_main_route_help(mock_context, mock_singleton):
    mock_context.message.content = "?oracle"
    # Help system now extracts docstrings
    await Routing.main_route(mock_context)
    mock_context.reply.assert_called()
    args = mock_context.reply.call_args[0][0]
    assert "Statistical analysis and predicted-values" in args


@pytest.mark.asyncio
async def test_main_route_help_general(mock_context, mock_singleton):
    mock_context.message.content = "?"
    await Routing.main_route(mock_context)
    mock_context.reply.assert_called()
    args = mock_context.reply.call_args[0][0]
    assert "Okysa Bot Help" in args
    assert "- `oracle`:" in args


@pytest.mark.asyncio
async def test_main_route_help_subcommand(mock_context, mock_singleton):
    mock_context.message.content = "?oracle versus"
    await Routing.main_route(mock_context)
    mock_context.reply.assert_called()
    args = mock_context.reply.call_args[0][0]
    assert "Compare the odds of two different selector rolls" in args


@pytest.mark.asyncio
async def test_main_route_diagnosis(mock_context, mock_singleton):
    # Test that ? with a non-command falls through to rollhandle (diagnosis mode)
    mock_context.message.content = "?3d10"
    with unittest.mock.patch(
        "Golconda.Routing.rollhandle", new_callable=AsyncMock
    ) as mock_rh:
        await Routing.main_route(mock_context)
        mock_rh.assert_called_once()
        # Verify it passed the full string (rollhandle/prepare handle the '?')
        args = mock_rh.call_args[0][0]
        assert args == "?3d10"
