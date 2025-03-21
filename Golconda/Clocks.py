import asyncio
import io
import os

import discord
import git
from matplotlib import pyplot as plt, patheffects

from Golconda.Storage import evilsingleton as singleton

SAVE_UPDATE_FIFO = "/tmp/save_update"


def make_piechart(current: str, maximum: str, title: str):
    # Convert the current and maximum values to integers
    current_value = int(current)
    max_value = int(maximum)

    # Prepare data for the pie chart
    data = [1] * max_value

    # Create a pie chart using matplotlib
    fig, ax = plt.subplots(figsize=(3, 3))

    colors = ["#051005"] * (max_value - current_value) + ["#00FF00"] * current_value

    # Create the pie chart
    ax.pie(
        data,
        startangle=90,
        wedgeprops={"edgecolor": "black", "linewidth": 2},
        colors=colors,
    )

    # Equal aspect ratio ensures the pie is drawn as a circle
    ax.axis("equal")
    title = ax.set_title(
        title, fontsize=14, fontweight="bold", color="black"
    )  # Black text color
    title.set_path_effects(
        [
            patheffects.withStroke(linewidth=3, foreground="white"),  # White outline
        ]
    )
    fig.patch.set_alpha(0.0)  # Figure background transparency
    ax.set_facecolor((0, 0, 0, 0))  # Axes background transparency
    # Save the pie chart to a BytesIO object
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)

    # Create a discord.File object for the image
    file = discord.File(buf, filename="pie_chart.png")

    return file


async def clockprocess(line: str):
    line, _ = line.rsplit("]", 1)
    line, maximum = line.rsplit("|", 1)
    line, current = line.rsplit("|", 1)
    title, _ = line.rsplit("[", 1)
    s = singleton()
    await s.client.get_channel(s.bridge_channel).send(
        file=make_piechart(current, maximum, title)
    )


async def trigger_async_function():
    repo = git.Repo("~/wiki")
    # Get the latest commit
    latest_commit = repo.head.commit

    # Get the diff of the latest commit (added lines)
    diff = latest_commit.diff(None, create_patch=True)
    # Loop through each file changed in the commit
    for change in diff:
        for line in change.diff.decode("utf-8").splitlines():
            if line.startswith("+") and "[clock|" in line:
                await clockprocess(line[1:])


async def handle():
    if not os.path.exists(SAVE_UPDATE_FIFO):
        os.mkfifo(SAVE_UPDATE_FIFO)
    while True:
        await asyncio.to_thread(wait_for_save_update)
        await trigger_async_function()


def wait_for_save_update():
    with open(SAVE_UPDATE_FIFO, "r") as fifo:
        fifo.readline()


async def clockhandle() -> None:
    await asyncio.create_task(handle())
