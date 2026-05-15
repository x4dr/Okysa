import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

from gamepack.Dice import DescriptiveError
from gamepack.WikiPage import WikiPage

log = logging.getLogger(__name__)

DISCORD_MSG_LIMIT = 2000
SAFE_MSG_LIMIT = 1990
DEFINES_KEY = "defines"
NOSSI_ACCOUNT_KEY = "NossiAccount"
DISCORD_ACCOUNT_KEY = "DiscordAccount"
CHAR_SHEET_CONF_KEY = "character_sheet"
BRIDGE_CONF_KEY = "bridge"
MC_POWERUSERS_KEY = "mc_powerusers"
REMINDER_STORAGE_KEY = "reminder"
NOT_REGISTERED_MSG = "You are not registered."
ACCESS_DENIED_MSG = "Access Denied!"
DEFAULT_TIMEZONE = "Europe/Berlin"


class Storage:
    client: Any  # The active bot client (Discord, Matrix, or a MultiClient)
    app: Any = None
    me: Any = None
    storage_path: Path
    storage: dict
    nossilink: str
    db: Optional[sqlite3.Connection] = None

    def __init__(self, setup_bot: Any):
        self.client = setup_bot
        self.me = getattr(setup_bot, "user", None)
        self.app = None
        self.roles = {}
        nossi = os.getenv("NOSSI")
        if not nossi:
            raise Exception("storage in env misconfigured: NOSSI is not set")
        self.nossilink = nossi.strip('"').strip("/")
        self.ollama = os.getenv("OLLAMA")
        self.connect_db("DATABASE")
        wikipath_env = os.getenv("WIKI")
        if not wikipath_env:
            raise Exception(f"storage in env misconfigured: WIKI={wikipath_env}")
        try:
            WikiPage.set_wikipath(Path(wikipath_env).expanduser())
        except (TypeError, ValueError):
            raise Exception(f"storage in env misconfigured: WIKI={wikipath_env}")

        storage_env = os.getenv("STORAGE")
        if not storage_env:
            raise Exception(f"storage in env misconfigured: STORAGE={storage_env}")
        try:
            self.storage_path = Path(storage_env).expanduser()
            self.read()
        except (TypeError, ValueError):
            raise Exception(f"storage in env misconfigured: STORAGE={storage_env}")
        self.bridge_channel = int(self.load_conf(BRIDGE_CONF_KEY, "channelid") or 0)
        self.page_cache = {}

    def getroles(self, guildid) -> list:
        if hasattr(self.client, "get_guild"):
            guild = self.client.get_guild(guildid)
            if guild:
                return guild.me.roles
        return []

    def connect_db(self, which: str) -> sqlite3.Connection:
        if self.db:
            return self.db
        dbpath = os.getenv(which) or ""
        if not dbpath or not Path(dbpath).exists():
            raise Exception(f"db in env misconfigured: {which}={dbpath}")
        try:
            self.db = sqlite3.connect(dbpath)
        except sqlite3.OperationalError:
            log.error(f"{dbpath} not valid")

        return self.db

    @classmethod
    async def create(cls, client: Any):
        self = cls(client)
        self.app = self.client.application
        return self

    def read(self) -> dict:
        if not self.storage_path.exists():
            self.storage: dict[str, Any] = {}
            return {}
        with self.storage_path.open() as file:
            self.storage = json.load(file)
        return self.storage

    def write(self) -> None:
        with self.storage_path.open("w") as file:
            json.dump(self.storage, file, indent=4, sort_keys=True)

    @property
    def allowed_channels(self) -> list[int | str]:
        return self.storage.setdefault("allowed_rooms", [])

    def load_conf(self, user, key):
        db = self.db
        res = db.execute(
            "SELECT value FROM configs WHERE user LIKE :user AND option LIKE :option;",
            dict(user=user, option=key),
        ).fetchone()
        return res[0] if res else None

    def load_entire_conf(self, user):
        res = self.db.execute(
            "SELECT option, value FROM configs WHERE user LIKE :user;", dict(user=user)
        ).fetchall()
        return {r[0]: r[1] for r in res} if res else {}

    def save_conf(self, user, option, value):
        if self.load_conf(user, option) is not None:
            self.db.execute(
                "UPDATE configs SET value = :value "
                "WHERE user LIKE :user AND option LIKE :option;",
                dict(user=user, option=option, value=value),
            )
        else:
            self.db.execute(
                "INSERT INTO configs(user,option,value) "
                "VALUES (:user, :option, :value);",
                dict(user=user, option=option, value=value),
            )
        self.db.commit()

    @staticmethod
    def get_data(file: str) -> str:
        p = Path(__file__)
        p = p.parent.parent / "Data" / file
        with open(p) as f:
            return f.read()

    def find_nossi_user_by_discord_id(self, discord_id: str) -> Optional[str]:
        # Search in configs for the discord ID. Handles "ID(name)" format.
        res = self.db.execute(
            "SELECT user FROM configs WHERE option = 'discord' AND value LIKE :did;",
            dict(did=f"{discord_id}%"),
        ).fetchone()
        return res[0] if res else None

    def store_message(self, message: Any):
        import re

        author_name = str(getattr(message.author, "display_name", message.author.name))
        content = message.content

        # Check if it's a webhook (author name is often "Okysa" or from a specific webhook ID)
        is_webhook = (
            getattr(message, "webhook_id", None) is not None or author_name == "Okysa"
        )

        if is_webhook:
            # 1. Try to extract mention <@ID> from the start
            mention_match = re.match(r"<@!?(\d+)>", content)
            if mention_match:
                discord_id = mention_match.group(1)
                nossi_user = self.find_nossi_user_by_discord_id(discord_id)
                if nossi_user:
                    author_name = nossi_user
                    # Optional: remove mention from content if it's purely for attribution
                    # but usually it's better to keep it if it's part of the roll resolution.
            else:
                # 2. Try to extract Nossinet username if prepended (format: "NAME: message")
                # Note: our new format for general chat is "MENTION\nMessage"
                # but if mention failed it might be "USERNAME\nMessage"
                name_match = re.match(r"^([a-zA-Z0-9_]+)\n", content)
                if name_match:
                    author_name = name_match.group(1)
                    content = content[
                        len(author_name) + 1 :
                    ]  # Remove name from content

        rendered = f"{author_name}\n{content}"

        self.db.execute(
            "INSERT INTO chatlogs(linenr, line, time, room) VALUES (:linenr, :line, :time, :room);",
            dict(
                linenr=message.id,
                line=rendered,
                time=message.created_at.timestamp(),
                room=message.channel.id,
            ),
        )
        self.db.commit()


_Storage: Storage | None = None


def evilsingleton() -> Storage:
    if not _Storage:
        raise DescriptiveError("not initialized yet")
    return _Storage


async def migrate(client: Any, user: Any):
    # 'user' should satisfy the BotUser protocol (has 'id' and '__str__')
    user_str = str(user)
    user_id = str(user.id)
    if (old := evilsingleton().storage.get(user_str, None)) and old != {"defines": {}}:
        evilsingleton().storage[user_id] = old
        del evilsingleton().storage[user_str]
        evilsingleton().write()
        outstanding = [
            x for x in evilsingleton().storage if isinstance(x, str) and "#" in x
        ]
        if (
            hasattr(client, "application")
            and client.application
            and client.application.owner
        ):
            await client.application.owner.send(
                f"migrated {user} to {user_id}. still outstanding: {outstanding}"
            )


async def setup(client: Any):
    global _Storage
    _Storage = await Storage.create(client)
