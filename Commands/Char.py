import logging
from typing import Type, OrderedDict
from uuid import uuid4

import hikari
import hikari.impl
from gamepack.Dice import DescriptiveError
from gamepack.MDPack import MDObj

from Golconda.Button import Button
from Golconda.Slash import Slash
from Golconda.Storage import evilsingleton
from Golconda.TextModal import TextModal
from Golconda.Tools import who_am_i, get_fen_char

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


@Button
async def char_nav(press: hikari.ComponentInteraction, path):
    path = [x for x in path.split(":") if x]
    e, r = charembed_path(press.message.embeds[0].url, path)
    await press.message.edit(embed=e, components=r)


sheetlink = "https://nosferatu.vampir.es/fensheet/"


def charembed_path(access: str, path: [str]):
    if access.startswith(sheetlink):
        c = access[len(sheetlink) :]
    else:
        author_storage = evilsingleton().storage.get(access)
        user = who_am_i(author_storage)
        c = evilsingleton().load_conf(user, "character_sheet")
    rows = [hikari.impl.ActionRowBuilder()]
    row = rows[0]
    chara = get_fen_char(c)
    embed = hikari.Embed(
        title=chara.Character.get("Name", "Unnamed character"),
        description="",
        url=f"{sheetlink}{c}",
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
            embed.add_field(str(k), str(v) or "-", inline=True)
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
        embed.description = chara.Notes.originalMD[:4000]
        rows = [hikari.impl.ActionRowBuilder()] + rows
        note_modal_button.add_to(rows[0], "Edit Notes", "")
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
            embed.add_field("experience", left, inline=True)
            embed.add_field("༜", right, inline=True)
    return embed, rows


edit_cache = {}


@TextModal
async def note_edit(cmd: hikari.ModalInteraction, modal: hikari.InteractionTextInput):
    author_storage = evilsingleton().storage.get(str(cmd.user))
    user = who_am_i(author_storage)
    c = evilsingleton().load_conf(user, "character_sheet")
    wikipage = list(evilsingleton().wikiload(c))
    to_edit = edit_cache.pop(modal.custom_id)
    ocurrences = wikipage[2].count(to_edit)
    if ocurrences == 1:
        wikipage[2] = wikipage[2].replace(to_edit, modal.value)
        evilsingleton().wikisave(wikipage, c, user)
    elif ocurrences > 1:
        await cmd.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            "sadly i couldn't find where your notes are in your sheet, as several places look like them. Make them "
            "unique and then you can edit them from here :)",
        )
    else:
        await cmd.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            "this went interestingly wrong. perhaps your notes were edited in some other way? i will send you your "
            "edits so you dont lose them :)",
        )
        await cmd.user.send(modal.value)
    str(cmd.user)


async def note_modal(event, author, param=None):
    author_storage = evilsingleton().storage.get(str(author))
    try:
        user = who_am_i(author_storage)
        c = evilsingleton().load_conf(user, "character_sheet")
        key = str(uuid4())
        mdobj = get_fen_char(c).Notes
        if param:
            for p in param.split(":"):
                mdobj = mdobj.children.get(p.strip(), MDObj.just_tables([]))
        edit_cache[key] = mdobj.originalMD[:4000]
        components = [
            note_edit.get_modal(
                key, "you are editing your actual notes!", edit_cache[key]
            )
        ]
        await event.create_modal_response("test", note_edit.route(), components)
    except DescriptiveError:
        await event.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE, author.mention + " ACCESS DENIED!"
        )


@Button
async def note_modal_button(press: hikari.ComponentInteraction, param: str):
    await note_modal(press, press.user, param)
    path = [x for x in param.split(":") if x]
    e, r = charembed_path(press.message.embeds[0].url, path)
    await press.message.edit(embed=e, components=r)


def register(slash: Type[Slash]):
    @slash.usermenu("Charactersheet")
    async def char_via_menu(cmd: Slash):
        user = await cmd.gettarget()
        embed, row = charembed_path(str(user), [])
        await cmd.respond_instant("", embed=embed, components=row)

    @slash.option("path", "':' separated path through subheadings", required=False)
    @slash.cmd("note", "Accesses your charactersheets notes")
    async def note(cmd: Slash):
        await note_modal(cmd.interaction, cmd.author, cmd.get("path"))

    @slash.cmd("char", "Accesses your charactersheet")
    async def char(cmd: Slash):
        title = cmd.get("site")
        path = [x for x in [title] + cmd.get("path", "").split(":") if x]
        embed, row = charembed_path(str(cmd.author), path)
        await cmd.respond_instant("", embed=embed, components=row)
