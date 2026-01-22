import logging

import discord
from gamepack.Dice import DescriptiveError
from gamepack.FenCharacter import FenCharacter
from gamepack.WikiCharacterSheet import WikiCharacterSheet

from Golconda.Storage import evilsingleton

logger = logging.getLogger(__name__)


def load_user_char_stats(user: str) -> dict:
    """Loads character statistics for a given NosferatuNet account."""
    char = load_user_char(user)
    if char:
        return char.stat_definitions()
    return {}


def load_user_char(user: str) -> FenCharacter | None:
    """Loads a FenCharacter object for a given NosferatuNet account."""
    c = evilsingleton().load_conf(user, "character_sheet")
    if c:
        try:
            return WikiCharacterSheet.load_locate(c).char
        except Exception as e:
            logger.error(f"Failed to load character sheet for {user}: {e}")
    return None


def who_am_i(author_storage: dict) -> str | None:
    """
    Resolves the NosferatuNet account name from author storage.
    Verifies that the Discord account is confirmed.
    """
    whoami = author_storage.get("NossiAccount")
    if whoami is None:
        return None

    checkagainst = evilsingleton().load_conf(whoami, "discord")
    discord_acc = author_storage.get("DiscordAccount")

    if discord_acc is None:
        author_storage["NossiAccount"] = "?"  # force resetup
        raise DescriptiveError(
            "Whoops, I have forgotten who you are, tell me again with slash-register please."
        )

    if checkagainst and discord_acc == checkagainst.split("(")[0]:
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
        raise DescriptiveError("You are not registered.")

    nossi_user = who_am_i(author_storage)
    if not nossi_user:
        raise DescriptiveError("You are not registered.")

    char_sheet = evilsingleton().load_conf(nossi_user, "character_sheet")
    if not char_sheet:
        raise DescriptiveError("No character sheet found for your account.")

    try:
        wiki = WikiCharacterSheet.load_locate(char_sheet)
        return wiki.char
    except Exception as e:
        logger.error(f"Error loading wiki character sheet: {e}")
        raise DescriptiveError("Failed to load your character sheet.")
