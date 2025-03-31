import asyncio
import io
import os

import discord
import git
import matplotlib.patheffects as patheffects
import matplotlib.pyplot as plt

from Golconda.Storage import evilsingleton as singleton

SAVE_UPDATE_FIFO = "/tmp/save_update"
running = []


def make_piechart(current: str, maximum: str, title: str):
    current_value = int(current)
    max_value = int(maximum)
    data = [1] * max_value
    colors = ["#051005"] * (max_value - current_value) + ["#00FF00"] * current_value

    # Initial figure size (1x1 for the pie chart, extra space added dynamically)
    fig, ax = plt.subplots(figsize=(1, 1))
    ax.pie(
        data,
        startangle=90,
        wedgeprops={"edgecolor": "black", "linewidth": 2},
        colors=colors,
    )
    ax.axis("equal")

    # Add title and get its bounding box
    title_obj = ax.set_title(title, fontsize=14, fontweight="bold", color="black")
    title_obj.set_path_effects(
        [patheffects.withStroke(linewidth=3, foreground="white")]
    )
    fig.canvas.draw()
    bbox = title_obj.get_window_extent(renderer=fig.canvas.get_renderer())
    title_height = bbox.height / fig.dpi  # Convert pixels to inches
    fig.set_size_inches(1, 1 + title_height + 0.2)  # 0.2 for padding
    ax.set_position(
        [0, title_height / (1 + title_height + 0.2), 1, 1 / (1 + title_height + 0.2)]
    )
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    buf.seek(0)
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
    running.append(asyncio.create_task(handle()))
