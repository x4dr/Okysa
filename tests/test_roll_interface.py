import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from Golconda import RollInterface
from gamepack.Dice import Dice


@pytest.fixture
def mock_storage():
    return {"defines": {}}


@pytest.mark.asyncio
async def test_prepare(mock_storage):
    msg = "1d20"
    mention = "<@123>"
    persist = mock_storage

    roll, comment, parser, errreport, dbg = await RollInterface.prepare(
        msg, mention, persist
    )

    assert roll == "1d20"
    assert comment == ""
    assert not errreport  # ? not present
    assert dbg == ""
    assert parser is not None


@pytest.mark.asyncio
async def test_prepare_with_comment(mock_storage):
    msg = "1d20 # for luck"
    mention = "<@123>"

    roll, comment, parser, errreport, dbg = await RollInterface.prepare(
        msg, mention, mock_storage
    )
    assert roll == "1d20"
    assert comment == " for luck"


@pytest.mark.asyncio
async def test_rollhandle_simple():
    send = AsyncMock()
    react = AsyncMock()
    persist = {"defines": {}}
    mention = "<@123>"

    res = await RollInterface.rollhandle("1d6", mention, send, react, persist)

    assert res is not None
    assert isinstance(res, Dice)
    assert res.result is not None
    send.assert_called()


def test_lastrolls():
    mention = "<@123>"
    dice = Dice(sides=20, amount=1)

    RollInterface.append_lastroll_for(mention, ("1d20", dice))
    rolls = RollInterface.get_lastrolls_for(mention)
    assert len(rolls) > 0
    assert rolls[-1][1] == dice


@pytest.mark.asyncio
async def test_process_roll_verbose():
    send = AsyncMock()
    mention = "<@123>"
    dice = Dice(sides=20, amount=1)
    parser = MagicMock()
    parser.triggers = {"verbose": True}
    parser.rolllogs = [dice]

    parser.rolllogs = [dice]

    with patch(
        "Golconda.RollInterface.get_reply", new_callable=AsyncMock
    ) as mock_get_reply:
        await RollInterface.process_roll(dice, parser, "1d20", "comment", send, mention)
        mock_get_reply.assert_called_once()


@pytest.mark.asyncio
async def test_rollhandle_author_error(mock_storage):
    persist = {"defines": {}}
    mention = "<@123>"
    send = AsyncMock()
    react = AsyncMock()

    # Mock timeout to raise DiceCodeError directly
    with patch("Golconda.RollInterface.timeout") as mock_timeout:
        from gamepack.DiceParser import DiceCodeError

        mock_timeout.side_effect = DiceCodeError("Invalid Roll")

        with pytest.raises(RollInterface.AuthorError):
            await RollInterface.rollhandle("?1d2X", mention, send, react, persist)
