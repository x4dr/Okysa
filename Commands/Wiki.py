import logging
import urllib.parse

import discord
from discord import app_commands
from gamepack.Dice import DescriptiveError
from gamepack.MDPack import MDObj

from Golconda.Storage import evilsingleton

logger = logging.getLogger(__name__)

NESTEDDICT = dict[str, "NESTEDDICT"]


def dict_search(wanted_key, tree: NESTEDDICT, path=tuple()):
    if isinstance(tree, list):
        for idx, el in enumerate(tree):
            yield from dict_search(wanted_key, el, path + (idx,))
    elif isinstance(tree, dict):
        for k in tree:
            if k == wanted_key:
                yield path + (k,)
        # you can add order of width-search by sorting result of tree.items()
        for k, v in tree.items():
            yield from dict_search(wanted_key, v, path + (k,))


class Wiki(discord.ui.View):
    wikilink = "https://nosferatu.vampir.es/wiki/"
    prefix = "wiki:"

    def __init__(self):
        super().__init__(timeout=None)
        self.embed = None

    @classmethod
    def make_from(cls, path: str):
        wiki = cls()
        path: [str] = [x for x in path.split(":") if x]
        title, tags, body = evilsingleton().wikiload(path[0])
        wikimd = MDObj.from_md(body, extract_tables=False)

        for step in path[1:]:
            newmd = wikimd.search_children(step)
            if newmd is None:
                raise DescriptiveError(
                    f"invalid step in path: {step}, options were :{', '.join(wikimd.children.keys())}"
                )
            wikimd = newmd
        embed = discord.Embed(
            title=title if title else path[0],
            description=wikimd.plaintext.strip().removeprefix("[TOC]").strip()[:4000],
            url="https://nosferatu.vampir.es/wiki/"
            + urllib.parse.quote(f"{path[0]}")
            + "#"
            + urllib.parse.quote(f"{path[-1].lower() if len(path) > 1 else ''}"),
            color=0x05F012,
        )
        if len(path) > 1:
            b = discord.ui.Button(
                label="⬆️",
                custom_id=f"{cls.prefix}{':'.join(path[:-1])}",
                style=discord.ButtonStyle.primary,
            )
            b.callback = nav_callback
            wiki.add_item(b)
        if len(wikimd.children) < 5:
            for sub in wikimd.children:
                b = discord.ui.Button(
                    label=sub,
                    custom_id=f"{cls.prefix}{':'.join(path+[sub])}",
                    style=discord.ButtonStyle.primary,
                )
                b.callback = nav_callback

                wiki.add_item(b)
        else:
            b = discord.ui.Select(custom_id=f"{Wiki.prefix}subheadings")
            b.callback = nav_callback
            for sub in wikimd.children[:25]:
                b.add_option(label=sub, value=f"{':'.join(path+[sub])}")
            wiki.add_item(b)
        if len(wikimd.children) > 25:
            embed.set_footer(
                text="Tags: "
                + " ".join(tags)
                + "\n"
                + f"More than 25 subheadings, <{len(wikimd.children)-25}> have been ommitted"
            )
        else:
            embed.set_footer(text="Tags: " + " ".join(tags) + "\n")
        wiki.embed = embed
        return wiki


async def nav_callback(
    interaction: discord.Interaction,
):
    path = interaction.data["custom_id"][len(Wiki.prefix) :]
    wiki = Wiki.make_from(path)
    await interaction.message.edit(embed=wiki.embed, view=wiki)
    # noinspection PyUnresolvedReferences
    await interaction.response.defer()


def register(tree: discord.app_commands.CommandTree):
    @app_commands.describe(
        site="the thing in the url after /wiki/", path="the path of headlines to follow"
    )
    @tree.command(name="wiki", description="Accesses the Nosferatu net wiki")
    async def wiki(interaction: discord.Interaction, site: str, path: str = ""):
        try:
            view = Wiki.make_from(f"{site}:{path}")
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("", embed=view.embed, view=view)
        except DescriptiveError as e:
            # noinspection PyUnresolvedReferences
            return await interaction.response.send_message(f"{e}", ephemeral=True)
