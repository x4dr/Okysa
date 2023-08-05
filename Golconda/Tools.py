import logging
import re
import time
from typing import Callable, Coroutine

import discord
from gamepack.Dice import DescriptiveError
from gamepack.DiceParser import fullparenthesis
from gamepack.FenCharacter import FenCharacter
from gamepack.WikiCharacterSheet import WikiCharacterSheet

from Golconda.Storage import evilsingleton

logger = logging.getLogger(__name__)

sent_messages = {}


def load_user_char_stats(user):
    char = load_user_char(user)
    if char:
        return char.stat_definitions()
    else:
        return {}


def load_user_char(user) -> FenCharacter | None:
    c = evilsingleton().load_conf(user, "character_sheet")
    if c:
        return WikiCharacterSheet.load_str(c).char


async def delete_replies(messageid: discord.Message.id):
    r: discord.Message
    if messageid in sent_messages:
        for r in sent_messages[messageid]["replies"]:
            await r.delete()
        del sent_messages[messageid]


def extract_comment(msg):
    comment = ""
    if isinstance(msg, str):
        msg = msg.split(" ")
    for i in reversed(range(len(msg))):
        if msg[i].startswith("//"):
            comment = " " + " ".join(msg[i:])[2:]
            msg = msg[:i]
            break
    return msg, comment


def mentionreplacer(client: discord.Client):
    def replace(m: re.Match):
        u: discord.User = client.get_user(int(m.group(1)))
        if u is None:
            logger.error(f"couldn't find user for id {m.group(1)}")
        return "@" + (u.name if u else m.group(1))

    return replace


def get_remembering_send(message: discord.Message):
    async def send_and_save(msg):
        sent = await message.reply(msg)
        sent_messages[message.id] = sent_messages.get(
            message.id, {"received": time.time(), "replies": []}
        )
        sent_messages[message.id]["replies"].append(sent)
        sent_messages[message.id]["received"] = time.time()
        byage = sorted(
            [(m["received"], k) for k, m in sent_messages.items()], key=lambda x: x[0]
        )
        for m, k in byage[100:]:
            del sent_messages[k]  # remove references for the oldes ones
        return sent

    return send_and_save


async def split_send(send, lines, i=0):
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


async def define(msg: str, message, author_storage: dict):
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
                for k, v in author_storage["defines"].items():
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
        author_storage["defines"][definition] = value
        await message.add_reaction("\N{THUMBS UP SIGN}")
        return None
    elif author_storage["defines"].get(msg, None) is not None:
        await message.author.send(author_storage["defines"][msg])
    else:
        await message.add_reaction("\N{THUMBS DOWN SIGN}")


async def undefine(msg: str, react: Callable[[str], Coroutine], persist: dict):
    """
    "undef <r>" removes all definitions for keys matching the regex
    """
    change = False
    for k in list(persist["defines"].keys()):
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


def splitpara(msg):
    sections = []
    while msg:
        para = fullparenthesis(msg, "&", "&", include=True)
        parapos = msg.find(para)
        sections += [msg[:parapos], para]
        msg = msg[parapos + len(para) :]
    return sections


async def replacedefines(msg, message, persist):
    oldmsg = ""
    author = str(message.author)
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
                for k, v in persist[author]["defines"].items():
                    pat = r"(^|\b)" + re.escape(k) + r"(\b|$)"
                    sections[i] = re.sub(pat, v, sections[i])
        msg = "".join(sections)
    return msg


def who_am_i(persist: dict) -> str | None:
    whoami = persist.get("NossiAccount", None)
    if whoami is None:
        # logger.error(f"whoami failed for {persist} ")
        return None
    checkagainst = evilsingleton().load_conf(whoami, "discord")
    discord_acc = persist.get("DiscordAccount", None)
    if discord_acc is None:  # should have been set up at the same time
        persist["NossiAccount"] = "?"  # force resetup
        raise DescriptiveError(
            "Whoops, I have forgotten who you are, tell me again with slash-register please."
        )
    if discord_acc == checkagainst.split("(")[0]:
        return whoami
    raise DescriptiveError(
        f"The NossiAccount {whoami} has not confirmed this discord account!"
    )


async def mutate_message(msg: str, author_storage: dict) -> (str, str):
    replacements: dict[str, str] = {}
    dbg = ""
    debugging = msg.startswith("?")
    whoami = who_am_i(author_storage)
    if whoami:
        if not replacements or msg.startswith("?"):
            newreplacements = load_user_char_stats(whoami)

            dbg += f"loading {len(set(newreplacements)-set(replacements))} stats from {whoami}'s character sheet\n"
            replacements = newreplacements
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
                    dbg += f"substituting {k} with {v} ==> `{msg}`\n"
                    break
        else:
            loopconstraint = 0  # no break means no replacements
    dbg += f"message after resolution:`{msg}`"
    return msg, dbg if debugging else ""


def dict_path(path, d):
    res = []
    for k, v in d.items():
        if isinstance(v, dict):
            res += dict_path(path + "." + k, v)
        else:
            res.append((path + "." + k, v))
    return res
