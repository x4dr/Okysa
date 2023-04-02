import logging
from collections import OrderedDict

import discord
from typing import Callable, List

from discord import app_commands

from Golconda.Storage import evilsingleton
from Golconda.Tools import who_am_i, get_fen_char

logger = logging.getLogger(__name__)


class Sheet(discord.ui.View):
    sheetlink = "https://nosferatu.vampir.es/fensheet/"
    prefix = "charsheet:"

    def __init__(self):
        super().__init__(timeout=None)
        self.embed = None

    def make_from(self, access, path):
        if access.startswith(self.sheetlink):
            c = access[len(self.sheetlink) :]
        elif "#" not in access:
            c = access
        else:
            author_storage = evilsingleton().storage.get(access)
            user = who_am_i(author_storage)
            c = evilsingleton().load_conf(user, "character_sheet")
        chara = get_fen_char(c)
        embed = discord.Embed(
            title=chara.Character.get("Name", "Unnamed character"),
            description="",
            url=f"{self.sheetlink}{c}",
            color=0x05F012,
        )

        self.add_nav_button("Character", "")
        self.add_nav_button("Categories", "categories")
        self.add_nav_button("Notes", "notes")
        self.add_nav_button("Experience", "experience")
        if not path:
            for i, (k, v) in enumerate(chara.Character.items()):
                if k.strip().lower == "name":
                    continue
                if i > 25:
                    break
                embed.add_field(name=str(k), value=str(v) or "-", inline=True)
        elif path[0] == "categories":
            ops = {}
            for i, (k, v) in enumerate(chara.Categories.items()):
                if k.strip().lower == "name":
                    continue
                if i > 25:
                    break
                embed.add_field(name=str(k), value=categoryformat(v), inline=True)
                ops[k] = k
            self.add_nav_select(
                "inspect",
                [
                    discord.SelectOption(label=x, value=x)
                    for x in chara.Categories.keys()
                ],
            )
        elif path[0] in chara.Categories:
            cat = chara.Categories[path[0]]
            left = ""
            right = ""
            dots = 5
            for h, section in cat.items():
                left += f"**_{h}_**\n"
                right += "_\n"
                for k, v in section.items():
                    left += f"{k}\n"
                    right += f"{maxdots(v, dots)}\n"
                dots = 3
            embed.add_field(name=path[0], value=left, inline=True)
            embed.add_field(name="༜", value=right, inline=True)
            self.add_nav_select(
                "inspect",
                [
                    discord.SelectOption(label=x, value=x)
                    for x in chara.Categories.keys()
                ],
            )

        elif path[0].lower() == "notes":
            embed.description = chara.Notes.originalMD[:4000]
            # note_modal_button.add_to(self, "Edit Notes", "")
        elif path[0].lower() in chara.experience_headings:
            xp = None
            for k, v in chara.Meta.items():
                if k.lower() in chara.experience_headings:
                    xp = v.tables
                    break
            if xp and xp[0]:
                left, right = "", ""
                for row in xp[0][1:]:
                    left += f"**{row[0]}**\n"
                    right += maxdots(row[2], 5) + "\n"
                embed.add_field(name="Experience", value=left, inline=True)
                embed.add_field(name="༜", value=right, inline=True)
        self.embed = embed
        return self

    def add_nav_button(self, name, key):
        item = discord.ui.Button(
            label=name, custom_id=self.prefix + key, row=len(self.children) // 5
        )
        item.callback = nav_callback
        self.add_item(item)

    async def note_modal_button(self, press: discord.Interaction, param: str):
        ...

        # await note_modal(press, press.user, param)
        # path = [x for x in param.split(":") if x]
        # e, r = charembed_path(press.message.embeds[0].url, path)
        # await press.message.edit(embed=e, components=r)

    def add_nav_select(self, default, options: List[discord.SelectOption]):
        item = discord.ui.Select(custom_id=default, options=options)
        item.callback = nav_callback
        self.add_item(item)


async def nav_callback(interaction: discord.Interaction):
    path = str(interaction.data["custom_id"][len(Sheet.prefix) :])
    path = [x for x in path.split(":") if x]
    embed = interaction.message.embeds[0] if interaction.message.embeds else None
    if not embed:
        return
    view = Sheet().make_from(embed.url, path)
    await interaction.message.edit(embed=view.embed, view=view)
    # noinspection PyUnresolvedReferences
    await interaction.response.defer()


def maxdots(v, maximum):
    try:
        return int(v) * "●" + "○" * (maximum - int(v))
    except ValueError:
        return v


def sectionformat(section: OrderedDict, maximum=3) -> str:
    result = ""
    for k, v in section.items():
        line = f"**{k}**:\t"
        line += maxdots(v, maximum)
        result += line + "\n"
    return result


def categoryformat(category: OrderedDict[str, OrderedDict[str, str]]) -> str:
    sections = (x for x in category.values())
    attributes = next(sections, {})
    result = sectionformat(attributes, 5)
    linelen = len(result.split("\n")[-1])
    result += "_" * linelen + "\n"
    return result + sectionformat(next(sections, {}))


def register(tree: discord.app_commands.CommandTree, callbacks: dict[str, Callable]):
    callbacks[Sheet.prefix] = nav_callback

    @tree.context_menu(name="Charactersheet")
    async def char_via_menu(interaction: discord.Interaction, user: discord.User):
        view = Sheet().make_from(str(user), "")
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("", embed=view.embed, view=view)

    @app_commands.describe(name="access a specific character")
    @tree.command(name="char")
    async def test(interaction: discord.Interaction, name: str = None):
        name = name or str(interaction.user)
        view = Sheet().make_from(name, "")
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("", embed=view.embed, view=view)
