import re
from random import random

import discord

from Golconda.Ollama import get_ollama_response

praise_phrases = [
    r"good(?: job| work| effort)?",
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


async def eastereggs(message: discord.Message):
    if message.guild:
        # Get the bot's member object in the current guild
        bot_name = message.guild.me.name
    else:
        bot_name = ""

    if message.author.bot:
        return
    praise_pattern = re.compile(
        rf"(?:{'|'.join(praise_phrases)})[, ]+{re.escape(bot_name)}", re.IGNORECASE
    )
    hate_pattern = re.compile(
        rf"(?:{'|'.join(hate_phrases)})[, ]*{re.escape(bot_name)}?", re.IGNORECASE
    )
    chance = 0
    if bot_name in message.content.lower():
        chance = 0.10
    if praise_pattern.search(message.content):
        await message.add_reaction("😳")
        chance += 0.15
    elif hate_pattern.search(message.content):
        await message.add_reaction("🖕")
        await message.add_reaction("😭")
        chance += 0.20
    if message.reference:
        ref = await message.channel.fetch_message(message.reference.message_id)
        chance += 0.05
        if ref.author == message.client.user:
            chance += 0.7
    r = random()
    print(r, chance)
    if r < chance:
        await get_ollama_response(message, message.client.storage)
