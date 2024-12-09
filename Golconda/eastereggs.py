import re

import discord

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


async def eastereggs(message: discord.Message):
    if message.guild:
        # Get the bot's member object in the current guild
        bot_member = message.guild.me
        bot_name = bot_member.name
    else:
        bot_name = ""
    praise_pattern = re.compile(
        rf"(?:{'|'.join(praise_phrases)})[, ]+{re.escape(bot_name)}", re.IGNORECASE
    )

    if praise_pattern.search(message.content):
        await message.add_reaction("😳")
