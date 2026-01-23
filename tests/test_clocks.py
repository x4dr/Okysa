import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import discord
from Golconda import Clocks


def test_make_piechart():
    with (
        patch("matplotlib.pyplot.subplots", return_value=(MagicMock(), MagicMock())),
        patch("matplotlib.pyplot.savefig"),
    ):
        file = Clocks.make_piechart("2", "5", "Title")
        assert isinstance(file, discord.File)
        assert file.filename == "pie_chart.png"


@pytest.mark.asyncio
async def test_clockprocess(mock_singleton, mock_channel):
    with (
        patch("Golconda.Clocks.singleton", return_value=mock_singleton),
        patch(
            "Golconda.Clocks.make_piechart", return_value=MagicMock(spec=discord.File)
        ) as mock_make,
    ):
        mock_singleton.client.get_channel.return_value = mock_channel
        mock_singleton.bridge_channel = 123

        await Clocks.clockprocess("Title[clock|2|5]")
        mock_make.assert_called_with("2", "5", "Title")
        mock_channel.send.assert_called()


@pytest.mark.asyncio
async def test_trigger_async_function(mock_singleton):
    mock_repo = MagicMock()
    mock_commit = MagicMock()
    mock_repo.head.commit = mock_commit

    mock_change = MagicMock()
    mock_change.diff.decode.return_value = "+Title[clock|2|5]"
    mock_commit.diff.return_value = [mock_change]

    with (
        patch("git.Repo", return_value=mock_repo),
        patch("Golconda.Clocks.clockprocess", new_callable=AsyncMock) as mock_proc,
    ):
        await Clocks.trigger_async_function()
        mock_proc.assert_called_with("Title[clock|2|5]")


@pytest.mark.asyncio
async def test_clockhandle():
    with (
        patch("os.path.exists", return_value=True),
        patch("asyncio.create_task") as mock_task,
    ):
        await Clocks.clockhandle()
        mock_task.assert_called()
        assert len(Clocks.running) > 0
