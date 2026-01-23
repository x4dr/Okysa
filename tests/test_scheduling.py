import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from Golconda import Scheduling


@pytest.fixture(autouse=True)
def clear_scheduling_functions():
    Scheduling.functions.clear()
    yield
    Scheduling.functions.clear()


def test_call_periodically():
    mock_func = AsyncMock()
    Scheduling.call_periodically(mock_func)
    assert (mock_func, []) in Scheduling.functions


def test_call_periodically_with():
    mock_func = AsyncMock()
    Scheduling.call_periodically_with(mock_func, [1, 2])
    assert (mock_func, [1, 2]) in Scheduling.functions


@pytest.mark.asyncio
async def test_periodic_loop():
    mock_func1 = AsyncMock(return_value=0.1)
    mock_func2 = AsyncMock(side_effect=Exception("Failed"))
    mock_func2.__name__ = "mock_func2"

    Scheduling.call_periodically(mock_func1)
    Scheduling.call_periodically(mock_func2)

    # We want to test that it calls the functions and sleeps
    # We'll mock asyncio.sleep to break the loop or just run it once
    with patch(
        "asyncio.sleep", side_effect=[None, asyncio.CancelledError]
    ) as mock_sleep:
        try:
            await Scheduling.periodic()
        except asyncio.CancelledError:
            pass

        mock_func1.assert_called()
        mock_func2.assert_called()
        mock_sleep.assert_called()
        # next_run should be min(15, 0.1) = 0.1
        # max(0.1, 1.0) = 1.0
        mock_sleep.assert_any_call(1.0)
