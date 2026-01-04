import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

import discord
from gamepack.Dice import DescriptiveError
from gamepack.WikiPage import WikiPage

log = logging.getLogger(__name__)


class Storage:
    client: discord.Client
    app: discord.Client | None
    me: discord.User
    storage_path: Path
    storage: dict
    nossilink: str
    db: sqlite3.Connection | None = None

    def __init__(self, setup_bot: discord.Client):
        self.client = setup_bot
        self.me: discord.User | None = self.client.user
        self.app = None
        self.roles = {}
        self.nossilink = os.getenv("NOSSI").strip('"').strip("/")
        self.ollama = os.getenv("OLLAMA")
        self.connect_db("DATABASE")
        try:
            WikiPage.set_wikipath(Path(os.getenv("WIKI")).expanduser())
        except Exception:
            raise Exception(f"storage in env misconfigured: WIKI={os.getenv('WIKI')}")
        try:
            self.storage_path = Path(os.getenv("STORAGE")).expanduser()
            self.read()
        except Exception:
            raise Exception(
                f"storage in env misconfigured: STORAGE={os.getenv('STORAGE')}"
            )
        self.bridge_channel = int(self.load_conf("bridge", "channelid") or 0)
        self.page_cache = {}

    def getroles(self, guildid) -> list[discord.Role]:
        guild = self.client.get_guild(guildid)
        if not guild:
            return []
        return guild.me.roles

    def connect_db(self, which: str) -> sqlite3.Connection:
        """db connection singleton"""

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
    async def create(cls, client: discord.Client):
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
            # pretty print, size is not a problem for now

    @property
    def allowed_channels(self) -> list[discord.abc.Snowflake | int]:
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

    # noinspection PyTypeChecker
    def store_message(self, message: discord.Message):
        rendered = (
            message.author.display_name + ": " + message.clean_content
        )  # PyTypeChecker: message.clean_content is str

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


async def migrate(client: discord.Client, user: discord.User):
    if (old := evilsingleton().storage.get(str(user), None)) and old != {"defines": {}}:
        evilsingleton().storage[str(user.id)] = old
        del evilsingleton().storage[str(user)]
        evilsingleton().write()
        outstanding = [
            x for x in evilsingleton().storage if isinstance(x, str) and "#" in x
        ]
        await client.application.owner.send(
            f"migrated {user} to {user.id}. still outstanding: {outstanding}"
        )


async def setup(client: discord.client):
    global _Storage
    _Storage = await Storage.create(client)
