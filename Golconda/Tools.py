import logging
import re
import time
from typing import Callable, Coroutine, Any, Awaitable
from gamepack.DiceParser import fullparenthesis

from Golconda.CharacterService import (
    load_user_char_stats,
    who_am_i,
)

logger = logging.getLogger(__name__)

sent_messages: dict[int, dict[str, Any]] = {}


async def delete_replies(messageid: int) -> None:
    if messageid in sent_messages:
        for r in sent_messages[messageid]["replies"]:
            await r.delete()
        del sent_messages[messageid]


def extract_comment(msg: str | list[str]) -> tuple[str | list[str], str]:
    comment = ""
    if isinstance(msg, str):
        msg = msg.split(" ")
    for i in reversed(range(len(msg))):
        if msg[i].startswith("//"):
            comment = " " + " ".join(msg[i:])[2:]
            msg = msg[:i]
            break
    return msg, comment


def mentionreplacer(bot_client) -> Callable[[re.Match], str]:
    def replace(m: re.Match) -> str:
        # bot_client should provide a way to get user info by ID
        # For now, we'll need to adapt this as it's very discord-specific
        if hasattr(bot_client, "get_user"):
            u = bot_client.get_user(int(m.group(1)))
            if u:
                return "@" + u.name
        logger.error(f"couldn't find user for id {m.group(1)}")
        return m.group(0)

    return replace


def get_remembering_send(
    message,
) -> Callable[[str], Awaitable[Any]]:
    async def send_and_save(msg: str) -> Any:
        sent = await message.reply(msg)
        sent_messages[message.id] = sent_messages.get(
            message.id, {"received": time.time(), "replies": []}
        )
        sent_messages[message.id]["replies"].append(sent)
        sent_messages[message.id]["received"] = time.time()
        byage = sorted(
            [(m["received"], k) for k, m in sent_messages.items()], key=lambda x: x[0]
        )
        for _, k in byage[100:]:
            del sent_messages[k]  # remove references for the oldest ones
        return sent

    return send_and_save


async def split_send(send: Callable, lines: list[str], i: int = 0) -> None:
    replypart = ""
    while i < len(lines):
        while len(replypart) + len(lines[i]) < 1950:
            replypart += lines[i] + "\n"
            i += 1
            if len(lines) <= i:
                break

        if replypart:
            await send("```" + replypart + "```")
            replypart = ""
        elif i < len(lines):
            await send("```" + lines[i][:1990] + "```")
            i += 1
            replypart = ""
        else:
            logger.error(f"aborting sending: unexpected state {i}, {lines}")
            break


async def define(msg: str, message, author_storage: dict) -> None:
    """
    "def a = b" defines 'a' to resolve to 'b'
    "def a" retrieves the definition of a
    "def =? retrieves all definitions"
    """
    if "=" in msg:
        question = re.compile(r"^=\s*\?")  # retrieve all?
        if question.match(msg):
            msg = question.sub(msg, "").strip()
            if not msg:
                defstring = "defines are:\n"
                for k, v in author_storage.setdefault("defines", {}).items():
                    defstring += "def " + k + " = " + v + "\n"
                for replypart in [
                    defstring[i : i + 1950] for i in range(0, len(defstring), 1950)
                ]:
                    await message.author.send(replypart)
                return None
        definition, value = [x.strip() for x in msg.split("=", 1)]
        if len(definition.strip()) < 1:
            await message.add_reaction("🇳")
            await message.add_reaction("🇴")
        author_storage.setdefault("defines", {})[definition] = value
        await message.add_reaction("\N{THUMBS UP SIGN}")
        return None
    elif author_storage.get("defines", {}).get(msg) is not None:
        await message.author.send(author_storage["defines"][msg])
    else:
        await message.add_reaction("\N{THUMBS DOWN SIGN}")


async def undefine(msg: str, react: Callable[[str], Coroutine], persist: dict) -> None:
    """
    "undef <r>" removes all definitions for keys matching the regex
    """
    change = False
    for k in list(persist.get("defines", {}).keys()):
        try:
            if re.match(msg + r"$", k):
                change = True
                del persist["defines"][k]
        except re.error:
            await react("🇷")
            await react("🇪")
            await react("🇬")
            await react("3️⃣")
            await react("🇽")
    if change:
        await react("\N{THUMBS UP SIGN}")
    else:
        await react("\N{BLACK QUESTION MARK ORNAMENT}")


def splitpara(msg: str) -> list[str]:
    sections = []
    while msg:
        para = fullparenthesis(msg, "&", "&", include=True)
        parapos = msg.find(para)
        sections += [msg[:parapos], para]
        msg = msg[parapos + len(para) :]
    return sections


async def replacedefines(msg: str, message, persist: dict) -> str:
    oldmsg = ""
    author = str(message.author.id)
    send = message.author.send
    counter = 0
    while oldmsg != msg:
        oldmsg = msg
        counter += 1
        if counter > 100:
            await send(
                "... i think i have some issues with the defines.\n" + msg[:1000]
            )
        sections = splitpara(msg)
        for i in range(len(sections)):
            if "&" not in sections[i]:
                for k, v in persist.get(author, {}).get("defines", {}).items():
                    pat = r"(^|\b)" + re.escape(k) + r"(\b|$)"
                    sections[i] = re.sub(pat, v, sections[i])
        msg = "".join(sections)
    return msg


foreignkey = re.compile(r"<@(\d+)>\s*\.\s*(.+?)\b")
name_foreignkey = re.compile(r"\b([a-zA-Z]\w*)\s*\.\s*([a-zA-Z]\w*)\b")


async def mutate_message(
    msg: str, storage: dict, mention: str, debugging: bool = False
) -> tuple[str, str]:
    replacements: dict[str, str] = {}
    dbg = ""
    debugging = debugging or msg.startswith("?")
    author_storage = storage.setdefault(str(mention[2:-1]), {})
    sheets = {}

    # resolve character name foreign keys (e.g. CharacterName.Stat)
    for m in name_foreignkey.finditer(msg):
        name = m.group(1)
        stat = m.group(2)
        for uid, data in storage.items():
            if (
                isinstance(data, dict)
                and data.get("NossiAccount", "").lower() == name.lower()
            ):
                msg = msg.replace(m.group(0), f"<@{uid}>.{stat}")
                break

    # keep checking and replacing foreign keys until none are left
    while foreignkey.search(msg):
        for m in foreignkey.finditer(msg):
            canonicalname = f"{m.group(1)}{m.group(2)}"
            msg = msg.replace(m.group(0), canonicalname)
            if m.group(1) in storage:
                whoarethey = who_am_i(storage[m.group(1)])
                if not sheets.get(whoarethey):
                    # make all keys lowercase
                    sheets[whoarethey] = {
                        k.lower(): v
                        for k, v in load_user_char_stats(whoarethey).items()
                    }
                    dbg += f"loading {len(sheets[whoarethey])} foreign stats from {whoarethey}'s character sheet\n"
                if m.group(2).lower() in sheets[whoarethey]:
                    replacements[canonicalname] = sheets[whoarethey][m.group(2).lower()]
                else:
                    dbg += f"failed to find {m.group(2)} in {whoarethey}'s character sheet\n"
            else:
                dbg += f"failed to find <@{m.group(1)}>\n"
    whoami = who_am_i(author_storage)
    if whoami:
        newreplacements = load_user_char_stats(whoami)
        dbg += f"loading {len(set(newreplacements) - set(replacements))} stats from {whoami}'s character sheet\n"
        replacements.update(newreplacements)
    # add in /override explicit defines to stats loaded from sheet
    replacements.update(author_storage.setdefault("defines", {}))

    loopconstraint = 100  # "recursion" depth
    used = []

    dbg += f"message before resolution: `{msg}`\n"
    while loopconstraint > 0:
        loopconstraint -= 1
        for k, v in replacements.items():
            if k not in used:
                msg, n = re.subn(
                    r"(?<!\w)" + re.escape(k) + r"(?!\w)", v, msg, flags=re.IGNORECASE
                )
                if n:
                    used.append(k)
                    dbg += f"substituting `{k}` with `{v}` ==> `{msg}`\n"
                    if foreignkey.search(msg):
                        dbg += "[interrupting to go resolve foreign keys]\n"
                        msg, debug = await mutate_message(
                            msg, storage, mention, debugging
                        )
                        dbg += debug
                        dbg += "\n[resuming]\n"
                    break

        else:
            loopconstraint = 0  # no break means no replacements
    dbg += f"message after resolution:`{msg}`"
    return msg, dbg if debugging else ""


def dict_path(path: str, d: dict) -> list[tuple[str, Any]]:
    res = []
    for k, v in d.items():
        if isinstance(v, dict):
            res += dict_path(path + "." + k, v)
        else:
            res.append((path + "." + k, v))
    return res
