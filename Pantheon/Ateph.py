import pickle
from pathlib import Path

import hikari


class Storage:
    bot: hikari.GatewayBot
    app: hikari.Application
    me: hikari.OwnUser
    datapersistence: Path
    storage: dict

    def __init__(self, setup_bot: hikari.GatewayBot, persistencepath: Path):
        self.bot = setup_bot
        self.me = self.bot.get_me()
        self.datapersistence = persistencepath
        self.app = None

    @classmethod
    async def create(cls, setup_bot: hikari.GatewayBot, persistencepath: Path):
        self = cls(setup_bot, persistencepath)
        self.app = await self.bot.rest.fetch_application()
        self.read()
        return self

    def read(self) -> dict:
        if not self.datapersistence.exists():
            self.storage = {}
            return {}
        with self.datapersistence.open("r") as file:
            self.storage = pickle.load(file)
        return self.storage

    def write(self) -> None:
        with self.datapersistence.open("w") as file:
            pickle.dump(self.storage, file)

    @property
    def allowed_channels(self) -> list[hikari.Snowflake]:
        return self.storage.get("allowed_rooms", [])


Ateph: Storage = None


def get_storage():
    return Ateph


async def setup(setup_bot: hikari.GatewayBot, persistencepath: Path):
    global Ateph
    Ateph = await Storage.create(setup_bot, persistencepath)
