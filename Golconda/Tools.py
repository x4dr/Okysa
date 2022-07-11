import logging
import re
import time
from typing import Callable, Coroutine

import bleach as bleach
import hikari
from gamepack.Cards import Cards
from gamepack.Dice import DescriptiveError
from gamepack.DiceParser import fullparenthesis
from gamepack.FenCharacter import FenCharacter
from gamepack.MDPack import traverse_md

from Golconda.Storage import evilsingleton

logger = logging.getLogger(__name__)

sent_messages = {}


def spells(page):
    result = None
    for spell in traverse_md(evilsingleton().wikiload(page)[2], "Zauber").split("###"):
        if result is None:
            result = {}  # skips section before first spell
            continue
        curspell = {}

        for line in spell.splitlines():
            if not line.strip():
                break
            if not curspell:
                curspell["Name"] = line.strip()
                continue
            if ":" not in line:
                raise DescriptiveError(
                    f"spell {curspell} has format issues in line {line}"
                )
            a, b = line.split(":", 1)
            curspell[a.strip("* ")] = b.strip()
        result[curspell["Name"].lower()] = curspell

    for r in result.values():
        for k, v in list(r.items()):
            if k == "Dedikation" or k == "Zauberkosten":
                ek = r.get("Effektive Kosten", {})
                for part in v.split(","):
                    part = part.strip().lower()
                    m = re.match(r"(\d+)\s*(ordnung|materie|energie|entropie|)", part)
                    if not m:
                        raise DescriptiveError(
                            f"spell {r['Name']} has format issues in {part}"
                        )
                    ek[m.group(2)] = ek.get(m.group(2), 0) + int(m.group(1))
                r["Effektive Kosten"] = ek
    return result


def get_fen_char(c: str) -> FenCharacter | None:
    s = evilsingleton()
    try:
        page = s.wikiload(c)
        char = FenCharacter.from_md(bleach.clean(page[2]))
        return char
    except DescriptiveError:
        return None  # these have to be diagnosed in other places


def load_user_char_stats(user):
    char = load_user_char(user)
    if char:
        return char.stat_definitions()
    else:
        return {}


def load_user_char(user) -> FenCharacter | None:
    c = evilsingleton().load_conf(user, "character_sheet")
    if c:
        return get_fen_char(c)


async def delete_replies(messageid: hikari.Message.id):
    r: hikari.Message
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


def mentionreplacer(client: hikari.GatewayBot):
    def replace(m: re.Match):
        u: hikari.User = client.cache.get_user(int(m.group(1)))
        if u is None:
            logger.error(f"couldn't find user for id {m.group(1)}")
        return "@" + (u.username if u else m.group(1))

    return replace


def get_remembering_send(message: hikari.Message):
    async def send_and_save(msg):
        # sent = await message.channel.send(msg)
        sent = await message.respond(msg, mentions_reply=True, reply=True)
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


async def cardhandle(msg, message, persist, send):
    def form(inp):
        if isinstance(inp, dict):
            outp = ""
            for k, j in inp.items():
                outp += "\n" + str(k) + ": " + form(j)
            return outp
        elif isinstance(inp, list):
            return ", ".join(inp)
        elif isinstance(inp, str):
            return inp
        else:
            DescriptiveError("HUH?")

    command = msg.split(":")[1]
    par = ":".join(msg.split(":")[2:])
    mention = message.author.mention
    deck: Cards | None = None
    whoami = None
    try:
        whoami = who_am_i(persist)
        if not whoami:
            return await send(mention + " Could not ascertain Identity!")

        deck = Cards.create_deck(evilsingleton().load_entire_conf(whoami))
        if command == "draw":
            await send(mention + " " + form(deck.elongate(deck.draw(par))))
        elif command == "spend":
            deck.spend(par)
        elif command == "returnfun":
            await send(mention + " " + form(deck.elongate(deck.pilereturn(par))))
        elif command == "dedicate":
            deck.dedicate(*par.split(":", 1))
            await message.add_reaction("\N{THUMBS UP SIGN}")
        elif command == "remove":
            deck.remove(par)
            await message.add_reaction("\N{THUMBS UP SIGN}")
        elif command == "undedicate":
            message = deck.undedicate(par)
            await send(
                mention
                + f" Affected Dedication{'s' if len(message) != 1 else ''}: "
                + ("\n".join(message) or "none")
            )
        elif command == "free":
            _, message = deck.free(par)
            await send(
                mention
                + f" Affected Dedication{'s' if len(message) != 1 else ''}: "
                + (",\n and ".join(message) or "none")
            )
        elif command == "help":
            await split_send(
                message.author.send, evilsingleton().get_data("card.help").splitlines()
            )
        elif command == "spells":
            await spellhandle(deck, whoami, par, send)
        else:
            infos = deck.renderlong
            if command in infos:
                await send(mention + " " + form(infos[command]))
            else:
                await send(mention + f" invalid command {command}")
        await message.add_reaction("\N{THUMBS UP SIGN}")
    except DescriptiveError as e:
        await send(mention + " " + str(e.args[0]))
    finally:
        if deck and whoami:
            for key, value in deck.serialize_deck(deck):
                evilsingleton().save_conf(whoami, key, value)


async def spellhandle(deck: Cards, whoami, par, send):
    spellbook = {}
    existing = {}
    power = deck.scorehand()
    spelltexts = load_user_char(whoami).Meta.get_storage("Zauber", ("", {}))[1]
    if not spelltexts:
        await send("No spells found")
    for spelltext in spelltexts.values():
        matches = re.findall(r"specific:(.*?):([^-]*?)(:-)?]", spelltext[0], flags=re.I)
        for m in matches:
            school = m[0]
            spell = m[1].split(":")[-1]
            spellbook[school] = spellbook.get(school, spells(school))
            existing[school + ":" + spell] = spellbook[school].get_storage(
                spell.lower(), {"Name": spell, "Error": "?"}
            )

    if par == "all":
        res = "All Spells:\n"
        for spec, spelldict in existing.items():
            if not spelldict.get_storage("Name", None):
                continue
            sr = ", ".join(
                [
                    f"{v} {k}".strip()
                    for k, v in spelldict.get_storage("Effektive Kosten", {}).items()
                ]
            )
            res += f"specific:{str(spec) + ':-': <45}  {sr}\n"
        await split_send(send, res.splitlines())
    elif par == "":
        res = "Available Spells:\n"
        for spec, spelldict in existing.items():
            if not spelldict.get_storage("Name", None):
                continue
            spelltime = spelldict.get_storage("Zauberzeit", "0").strip()
            if "Runde" in spelltime or spelltime == "0":
                if satisfy(power, spelldict.get_storage("Effektive Kosten")):
                    sr = ", ".join(
                        [
                            (str(v) + " " + k).strip()
                            for k, v in spelldict.get_storage(
                                "Effektive Kosten", {}
                            ).items()
                        ]
                    )
                    res += (
                        f"{spelldict['Name']: <25} "
                        f"{sr: >25} "
                        f"\n(specific:{spec}:-)\n"
                    )
        await split_send(send, res.splitlines())
    else:
        await send(f"unknown spell command: '{par}'")


def satisfy(source, reqs):
    if not reqs:
        return True
    for req, val in reqs.items():
        if not req:
            if sum(source.values()) < val:
                return False
        elif source.get_storage(req.lower(), 0) < val:
            return False

    else:
        return True


def available_transitions():
    pass


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
        if re.match(msg + r"$", k):
            change = True
            del persist["defines"][k]
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


def who_am_i(persist):
    whoami = persist.get("NossiAccount", None)
    if whoami is None:
        # logger.error(f"whoami failed for {persist} ")
        return None
    checkagainst = evilsingleton().load_conf(whoami, "discord")
    discord_acc = persist.get("DiscordAccount", None)
    if discord_acc is None:  # should have been set up at the same time
        persist["NossiAccount"] = "?"  # force resetup
        raise DescriptiveError(
            "Whoops, I have forgotten who you are, tell me again please."
        )
    if discord_acc == checkagainst:
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
