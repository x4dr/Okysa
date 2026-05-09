import re
from functools import lru_cache
from random import random
from typing import Any

from Golconda.Ollama import get_ollama_response
from Golconda.Storage import evilsingleton

praise_phrases = [
    r"good(?: job| work| effort| girl| boy)?",
    r"well done",
    r"thank you(?: so much| a lot)?",
    r"amazing(?: work| job)?",
    r"excellent(?: effort| work)?",
    r"great(?: job| work)?",
    r"nice(?: job| work)?",
    r"you're the best",
    r"keep it up",
    r"i love you",
]

hate_phrases = [
    r"fuck(?: you| off)?",
    r"i hate(?: you| it)?",
    r"you're (?:awful|terrible|horrible|the worst)",
    r"(?:stupid|dumb|idiot|moron)",
    r"go away",
    r"shut up",
    r"nobody likes you",
    r"why are you here",
    r"useless bot",
    r"(?:kill|delete) yourself",
    r"(go )?\bkys\b",
    r"(go )?fuck you(rself)?",
    r"bad",
    r"bitch",
]


@lru_cache
def me():
    return evilsingleton().me


async def eastereggs(message: Any):
    """Scan message for easter eggs.
    'message' should satisfy the BotMessage protocol.
    """
    # bot_name logic needs to be platform specific or generic
    bot_name = str(evilsingleton().me.name)

    if hasattr(message.author, "bot") and message.author.bot:
        return

    praise_pattern = re.compile(
        rf"(?:{'|'.join(praise_phrases)})[, ]+{re.escape(bot_name)}", re.IGNORECASE
    )
    hate_pattern = re.compile(
        rf"(?:{'|'.join(hate_phrases)})[, ]*{re.escape(bot_name)}?", re.IGNORECASE
    )
    chance = 0
    if bot_name and bot_name.lower() in message.content.lower():
        chance = 0.10
    if praise_pattern.search(message.content):
        await message.add_reaction("😳")
        chance += 0.15
    elif hate_pattern.search(message.content):
        await message.add_reaction("🖕")
        await message.add_reaction("😭")
        chance += 0.20

    # Platform-agnostic reply detection
    if message.reply_to_id:
        chance += 0.05

    r = random()
    if r < chance:
        await get_ollama_response(message)
