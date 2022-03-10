import json
import logging
import os
import sqlite3
from pathlib import Path

import hikari
import lavalink
from gamepack.Dice import DescriptiveError

log = logging.getLogger(__name__)


class Storage:
    bot: hikari.GatewayBot
    app: hikari.Application | None
    me: hikari.OwnUser
    storage_path: Path
    storage: dict
    lavalink: lavalink.Client
    db: sqlite3.Connection | None = None

    def __init__(self, setup_bot: hikari.GatewayBot):
        self.bot = setup_bot
        self.me: hikari.OwnUser = self.bot.get_me()
        self.app = None
        self.connect_db("DATABASE")
        try:
            self.wikipath = Path(os.getenv("WIKI")).expanduser()
        except Exception:
            raise Exception(
                f"storage in env misconfigured: STORAGE={os.getenv('STORAGE')}"
            )
        try:
            self.storage_path = Path(os.getenv("STORAGE")).expanduser()
            self.read()
        except Exception:
            raise Exception(
                f"storage in env misconfigured: STORAGE={os.getenv('STORAGE')}"
            )
        self.page_cache = {}

    def connect_db(self, which: str) -> sqlite3.Connection:
        """db connection singleton"""

        if self.db:
            return self.db
        dbpath = os.getenv(which)
        if not Path(dbpath).exists():
            raise Exception(f"db in env misconfigured: {which}={dbpath}")
        try:
            self.db = sqlite3.connect(dbpath)
        except sqlite3.OperationalError:
            log.error(f"{dbpath} not valid")

        return self.db

    @classmethod
    async def create(cls, setup_bot: hikari.GatewayBot):
        self = cls(setup_bot)
        self.app = await self.bot.rest.fetch_application()
        # self.lavalink = lavalink.Client(self.me.id)
        # self.lavalink.add_node(
        #    "localhost", 2333, "youshallnotpass", "eu", "default-node"
        # )
        return self

    def read(self) -> dict:
        if not self.storage_path.exists():
            self.storage = {}
            return {}
        with self.storage_path.open() as file:
            self.storage = json.load(file)
        return self.storage

    def write(self) -> None:
        with self.storage_path.open("w") as file:
            json.dump(self.storage, file, indent=4, sort_keys=True)
            # pretty print, size is not a problem for now

    @property
    def allowed_channels(self) -> list[hikari.Snowflake]:
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

    def make_wiki_path(self, page: str | Path) -> Path:
        if isinstance(page, str):
            return self.wikipath / (page + ".md")
        elif isinstance(page, Path):
            return self.wikipath / page.with_suffix(".md")
        raise ValueError(f"page {page} is not valid", page)

    def wiki_latest(self, page: Path) -> bool:
        page = self.make_wiki_path(page)
        c = self.page_cache.get(page)
        if c and os.path.getmtime(page) == c[1]:
            return True

    def pagetime(self, page: str) -> float:  # for external caching
        return os.path.getmtime(self.make_wiki_path(page))

    def wikiload(self, page: str | Path) -> [str, [str], str]:
        """
        loads page from wiki
        :param page: name of page
        :return: title, tags, body
        """
        p = self.make_wiki_path(page)
        if self.wiki_latest(p):
            return self.page_cache.get(page)[0]
        try:
            with p.open() as f:
                mode = "meta"
                title = ""
                tags = []
                body = ""
                for line in f.readlines():
                    if mode:
                        if line.startswith("tags:"):
                            tags += [
                                t for t in line.strip("tags:").strip().split(" ") if t
                            ]
                            continue
                        if line.startswith("title:"):
                            title = line.strip("title:").strip()
                            continue
                        if not line.strip():
                            mode = ""
                    body += line
                self.page_cache[page] = (title, tags, body), os.path.getmtime(p)
                return title, tags, body
        except FileNotFoundError:
            raise DescriptiveError(page + " not found in wiki.")

    @staticmethod
    def get_data(file: str) -> str:
        p = Path(__file__)
        p = p.parent.parent / "Data" / file
        with open(p) as f:
            return f.read()


_Storage: Storage | None = None


def getstorage() -> Storage:
    if not _Storage:
        raise DescriptiveError("not initialized yet")
    return _Storage


async def setup(setup_bot: hikari.GatewayBot):
    global _Storage
    _Storage = await Storage.create(setup_bot)
