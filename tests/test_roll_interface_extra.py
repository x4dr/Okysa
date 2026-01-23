import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from Golconda import RollInterface
from gamepack.Dice import Dice


@pytest.mark.asyncio
async def test_chunk_reply():
    send = AsyncMock()
    await RollInterface.chunk_reply(send, "Pre: ", "a" * 3000)
    assert send.call_count == 2
    send.assert_any_call("Pre: ```" + "a" * (1990 - len("Pre: ")) + "```")


@pytest.mark.asyncio
async def test_get_reply_resonance(mock_message):
    send = AsyncMock(return_value=mock_message)
    dice = Dice(sides=10, amount=5)
    # Force some resonance
    dice.r = [1, 1, 5, 5, 10]
    dice.returnfun = "1,1,5,5,10@"

    with (
        patch("Golconda.RollInterface.minimum_expected", return_value=100.0),
        patch("Golconda.RollInterface.maximum_expected", return_value=0.0),
    ):
        await RollInterface.get_reply("<@123>", "comment", "msg", send, "reply", dice)
        # Should add reactions for resonance and expected values
        assert mock_message.add_reaction.called


def test_expected_values():
    dice = Dice(sides=10, amount=5)
    dice.returnfun = "1,2,3,4,5@"
    dice.rerolls = 0

    with (
        patch("Golconda.RollInterface.fastdata", return_value=[1, 2, 3, 4, 5]),
        patch("Golconda.RollInterface.avgdev", return_value=(3.0, 1.0)),
    ):
        assert RollInterface.minimum_expected(dice) == 2.0
        assert RollInterface.maximum_expected(dice) == 4.0


@pytest.mark.asyncio
async def test_rollhandle_timeout():
    send = AsyncMock()
    react = AsyncMock()
    persist = {"defines": {}}

    mock_parser = MagicMock()
    # Force the timeout error to be raised regardless of __debug__
    mock_parser.do_roll.side_effect = RollInterface.multiprocessing.TimeoutError()

    with patch(
        "Golconda.RollInterface.prepare",
        return_value=("1d20", "", mock_parser, False, ""),
    ):
        await RollInterface.rollhandle("1d20", "<@123>", send, react, persist)
        react.assert_called_with("\U000023f0")


@pytest.mark.asyncio
async def test_rollhandle_value_error():
    send = AsyncMock()
    react = AsyncMock()
    persist = {"defines": {}}

    mock_parser = MagicMock()
    mock_parser.do_roll.side_effect = ValueError("Bad value")

    with patch(
        "Golconda.RollInterface.prepare",
        return_value=("'1d20'", "", mock_parser, False, ""),
    ):
        # Should react with flip because of quotes
        await RollInterface.rollhandle("'1d20'", "<@123>", send, react, persist)
        react.assert_called_with("🙃")


@pytest.mark.asyncio
async def test_rollhandle_message_return():
    send = AsyncMock()
    react = AsyncMock()
    persist = {"defines": {}}

    from gamepack.DiceParser import MessageReturn

    mock_dice = MagicMock(spec=Dice)
    mock_dice.roll_v.return_value = "10"
    mock_dice.name = "1d20"
    mock_dice.comment = ""
    mock_dice.returnfun = ""

    mock_parser = MagicMock()
    mock_parser.do_roll.side_effect = MessageReturn("Hello")

    with patch(
        "Golconda.RollInterface.prepare",
        return_value=("1d20", "", mock_parser, False, ""),
    ):
        await RollInterface.rollhandle("1d20", "<@123>", send, react, persist)
        send.assert_called()
        assert "Hello" in send.call_args[0][0]
