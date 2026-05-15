import logging

import discord
from gamepack.Dice import DescriptiveError
from gamepack.FenCharacter import FenCharacter
from gamepack.WikiCharacterSheet import WikiCharacterSheet

from Golconda.Storage import (
    evilsingleton,
    NOSSI_ACCOUNT_KEY,
    DISCORD_ACCOUNT_KEY,
    NOT_REGISTERED_MSG,
    CHAR_SHEET_CONF_KEY,
)

logger = logging.getLogger(__name__)


def load_user_char_stats(user: str) -> dict:
    """Loads character statistics for a given NosferatuNet account."""
    char = load_user_char(user)
    if char:
        return char.stat_definitions()
    return {}


def load_user_char(user: str) -> FenCharacter | None:
    c = evilsingleton().load_conf(user, CHAR_SHEET_CONF_KEY)
    if c:
        try:
            return WikiCharacterSheet.load_locate(c).char
        except Exception as e:
            logger.error(f"Failed to load character sheet for {user}: {e}")
    return None


def who_am_i(author_storage: dict) -> str | None:
    whoami = author_storage.get(NOSSI_ACCOUNT_KEY)
    if whoami is None:
        return None

    import re

    checkagainst_raw = evilsingleton().load_conf(whoami, "discord")
    discord_id_match = (
        re.match(r"(\d+)", checkagainst_raw) if checkagainst_raw else None
    )
    checkagainst = discord_id_match.group(1) if discord_id_match else None

    discord_acc = author_storage.get(DISCORD_ACCOUNT_KEY)

    if discord_acc is None:
        author_storage[NOSSI_ACCOUNT_KEY] = "?"
        raise DescriptiveError(
            "Whoops, I have forgotten who you are, tell me again with slash-register please."
        )

    if checkagainst and discord_acc == checkagainst:
        return whoami

    raise DescriptiveError(
        f"The NossiAccount {whoami} has not confirmed this discord account!"
    )


def get_discord_user_char(user: discord.User | discord.Member) -> FenCharacter:
    """
    Gets the FenCharacter for a Discord user.
    Raises DescriptiveError if the user is not registered or confirmed.
    """
    author_storage = evilsingleton().storage.get(str(user.id))
    if not author_storage:
        raise DescriptiveError(NOT_REGISTERED_MSG)

    nossi_user = who_am_i(author_storage)
    if not nossi_user:
        raise DescriptiveError(NOT_REGISTERED_MSG)

    char_sheet = evilsingleton().load_conf(nossi_user, CHAR_SHEET_CONF_KEY)
    if not char_sheet:
        raise DescriptiveError("No character sheet found for your account.")

    try:
        wiki = WikiCharacterSheet.load_locate(char_sheet)
        return wiki.char
    except Exception as e:
        logger.error(f"Error loading wiki character sheet: {e}")
        raise DescriptiveError("Failed to load your character sheet.")
