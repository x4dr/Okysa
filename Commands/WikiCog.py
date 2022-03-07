import logging
from typing import Type

import hikari
import hikari.impl
from gamepack import MDPack
from gamepack.Dice import DescriptiveError

from Golconda.Button import Button
from Golconda.Slash import Slash
from Golconda.Storage import getstorage

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


def register(slash: Type[Slash]):
    def wikiembed_path(site: [str, [str], str], path: [str]):
        row = hikari.impl.ActionRowBuilder()
        firsttext, tree = MDPack.split_md(site[2])
        firsttext = firsttext.strip().removeprefix("[TOC]").strip()
        for step in path[1:]:
            firsttext, newtree = tree.get(step.strip(), (None, None))
            if firsttext is None:
                raise DescriptiveError(
                    f"invalid step in path: {step}, options were :{', '.join(tree.keys())}"
                )
            tree = newtree
        embed = hikari.Embed(
            title=site[0],
            description="Tags: " + " ".join(site[1]) + "\n" + firsttext,
            url=f"https://nosferatu.vampir/wiki/{path[0]}#{path[-1].lower() if len(path) > 1 else ''}",
            color=0x05F012,
        )
        if len(path) > 1:
            navigate.add_to(row, "..", f"{':'.join(path[:-1])}")
        for sub in tree.keys():
            navigate.add_to(row, sub, f"{':'.join(path+[sub])}")

        return embed, row

    @slash.option(
        "path",
        "the path of headlines to follow",
        required=False,
    )
    @slash.option("site", "the thing in the url after /wiki/")
    @slash.cmd("wiki", "Accesses the Nosferatu net wiki")
    async def wiki(cmd: Slash):
        s = getstorage()
        title = cmd.get("site")
        path = [x for x in [title] + cmd.get("path", "").split(":") if x]
        try:
            site = s.wikiload(title)
            embed, row = wikiembed_path(site, path)
        except DescriptiveError as e:
            return await cmd.respond_instant_ephemeral(f"{e}")
        await cmd.respond_instant("", embed=embed, component=row)

    @Button
    async def navigate(press: hikari.ComponentInteraction, path):
        s = getstorage()
        path = path.split(":")
        e, r = wikiembed_path(s.wikiload(path[0]), path)
        await press.message.edit(embed=e, component=r)
