import logging
import os
import sys
import asyncio

if not hasattr(asyncio, "coroutine"):
    asyncio.coroutine = lambda x: x
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

import discord
from Frontends.DiscordFrontend import DiscordBot
from Frontends.MatrixFrontend import MatrixBot

# Load environment variables from .env file
load_dotenv()


def configure_logging() -> None:
    log = logging.getLogger()
    log.setLevel(logging.INFO if "debug" not in sys.argv else logging.DEBUG)

    loc = ([x[4:] for x in sys.argv if x.startswith("log=")][:1] or ["./okysa.log"])[0]

    rfh = RotatingFileHandler(
        loc,
        maxBytes=521288,  # 512 KB
        encoding="utf-8",
        backupCount=10,
    )

    ff = logging.Formatter(
        "[%(asctime)s] %(levelname)s ||| %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    rfh.setFormatter(ff)
    log.addHandler(rfh)
    log.addHandler(logging.StreamHandler(sys.stdout))


async def main():
    configure_logging()

    tasks = []

    # Discord Setup
    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        token_path = os.path.expanduser("~/token.discord")
        if os.path.exists(token_path):
            with open(token_path, "r") as f:
                discord_token = f.read().strip()

    if discord_token:
        intents = discord.Intents.default()
        intents.message_content = True
        discord_bot = DiscordBot(intents=intents)
        tasks.append(discord_bot.start(discord_token))
        logging.info("Initialized Discord frontend")
    else:
        logging.warning("No Discord token found, skipping Discord frontend")

    # Matrix Setup
    matrix_server = os.getenv("MATRIX_SERVER")
    matrix_user = os.getenv("MATRIX_USER")
    matrix_pass = os.getenv("MATRIX_PASS")

    if matrix_server and matrix_user and matrix_pass:
        try:
            matrix_bot = MatrixBot(matrix_server, matrix_user, matrix_pass)
            tasks.append(matrix_bot.run())
            logging.info("Initialized Matrix frontend")
        except ImportError:
            logging.error(
                "Matrix frontend requested but simplematrixbotlib is not installed."
            )
    else:
        logging.warning("Matrix credentials missing, skipping Matrix frontend")

    if not tasks:
        logging.error("No frontends configured. Exiting.")
        return

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
