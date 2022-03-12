import logging
from typing import Type, OrderedDict

import hikari
import hikari.impl

from Golconda.Button import Button
from Golconda.Slash import Slash
from Golconda.Storage import getstorage
from Golconda.Tools import who_am_i, load_user_char

logger = logging.getLogger(__name__)


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


def register(slash: Type[Slash]):
    def charembed_path(author: str, path: [str]):
        rows = [hikari.impl.ActionRowBuilder()]
        row = rows[0]
        author_storage = getstorage().storage.get(author)
        user = who_am_i(author_storage)
        chara = load_user_char(user)
        c = getstorage().load_conf(user, "character_sheet")
        embed = hikari.Embed(
            title=chara.Character.get("Name", "Unnamed character"),
            description="",
            url=f"https://nosferatu.vampir/fensheet/{c}",
            color=0x05F012,
        )
        char_nav.add_to(row, "Character", "")
        char_nav.add_to(row, "Categories", "categories")
        char_nav.add_to(row, "Notes", "notes")
        char_nav.add_to(row, "Experience", "Experience")
        if not path:
            for i, (k, v) in enumerate(chara.Character.items()):
                if k.strip().lower == "name":
                    continue
                if i > 25:
                    break
                embed.add_field(str(k), str(v), inline=True)
        elif path[0] == "categories":
            ops = []
            for i, (k, v) in enumerate(chara.Categories.items()):
                if k.strip().lower == "name":
                    continue
                if i > 25:
                    break
                embed.add_field(str(k), categoryformat(v), inline=True)
                ops.append((str(k), str(k)))
            rows.append(
                char_nav.as_select_menu(
                    "inspect", ((x, x) for x in chara.Categories.keys())
                )
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
            embed.add_field(path[0], left, inline=True)
            embed.add_field("༜", right, inline=True)
            rows.append(
                char_nav.as_select_menu(
                    "inspect", ((x, x) for x in chara.Categories.keys())
                )
            )

        elif path[0].lower() == "notes":
            embed.description = chara.Notes or "notes are currently not implemented yet"
        elif path[0].lower() in chara.experience_headings:
            xp = None
            for k, v in chara.Meta.items():
                if k.lower() in chara.experience_headings:
                    xp = v[2]
                    break
            if xp and xp[0]:
                left, right = "", ""
                for row in xp[0][1:]:
                    left += f"**{row[0]}**\n"
                    right += maxdots(row[2], 5) + "\n"

                embed.add_field("experience", left, inline=True)
                embed.add_field("༜", right, inline=True)

        return embed, rows

    @slash.cmd("char", "Accesses your charactersheet")
    async def char(cmd: Slash):
        title = cmd.get("site")
        path = [x for x in [title] + cmd.get("path", "").split(":") if x]
        embed, row = charembed_path(str(cmd.author), path)
        await cmd.respond_instant("", embed=embed, components=row)

    @Button
    async def char_nav(press: hikari.ComponentInteraction, path):
        path = [x for x in path.split(":") if x]
        e, r = charembed_path(str(press.user), path)
        await press.message.edit(embed=e, components=r)
