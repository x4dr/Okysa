import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

import hikari

import Commands
from Golconda.TextModal import TextModal
from Golconda.Button import Button
from Golconda.Rights import allowed
from Golconda.Routing import main_route
from Golconda.Slash import Slash
from Golconda.Storage import setup, evilsingleton
from Golconda.Tools import delete_replies

Slash.register(Commands.get_register_functions())

if os.name != "nt":
    import uvloop

    uvloop.install()


def configure_logging() -> None:
    log = logging.getLogger("root")
    log.setLevel(logging.INFO if "debug" not in sys.argv else logging.DEBUG)

    loc = ([x[4:] for x in sys.argv if x.startswith("log=")][:1] or ["./okysa.log"])[0]

    rfh = RotatingFileHandler(
        loc,
        maxBytes=521288,  # 512KB
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


if __name__ == "__main__":
    configure_logging()

with open(os.path.expanduser("~/token.discord"), "r") as tokenfile:
    bot = hikari.GatewayBot(token=tokenfile.read().strip())


@bot.listen(hikari.StartedEvent)
async def startup(event: hikari.StartedEvent):
    app = await event.app.rest.fetch_application()

    await bot.update_presence(status=f"awoken {datetime.now().strftime('%H:%M:%S')}")
    await event.app.rest.set_application_commands(app, Slash.all(event.app.rest))
    await app.owner.send("Okysa has decended")
    #     + str(", ".join(x.name for x in bot.cache.get_guilds_view().values()))
    # )
    logging.info(f"Owner is {app.owner}")
    await setup(bot)


@bot.listen()
async def on_edit(event: hikari.MessageUpdateEvent) -> None:
    """Listen for messages being edited."""
    if event.is_human and await allowed(event.message):
        await main_route(event)


@bot.listen()
async def on_message(event: hikari.MessageCreateEvent) -> None:
    """Listen for messages being created."""
    if event.is_human and await allowed(event.message):
        await main_route(event)
    elif (event.message.content or "").strip().startswith("?"):
        logging.error(f"not listening in {event.message.channel_id}")


@bot.listen()
async def on_delete(event: hikari.MessageDeleteEvent) -> None:
    """Listen for messages being created."""
    await delete_replies(event.message_id)


# On voice state update the bot will update the lavalink node
@bot.listen(hikari.VoiceStateUpdateEvent)
async def voice_state_update(event: hikari.VoiceStateUpdateEvent):
    await evilsingleton().lavalink.raw_voice_state_update(
        event.guild_id,
        event.state.user_id,
        event.state.session_id,
        event.state.channel_id,
    )


@bot.listen(hikari.VoiceServerUpdateEvent)
async def voice_server_update(event: hikari.VoiceServerUpdateEvent):
    logging.debug(event)
    await evilsingleton().lavalink.raw_voice_server_update(
        event.guild_id,
        event.endpoint,
        event.token,
    )


@bot.listen(hikari.InteractionCreateEvent)
async def on_interaction_create(event: hikari.InteractionCreateEvent):
    if isinstance(event.interaction, hikari.ComponentInteraction):
        return await Button.route(event.interaction)
    if isinstance(event.interaction, hikari.CommandInteraction):
        return await Slash.route(event.interaction)
    if isinstance(event.interaction, hikari.ModalInteraction):
        return await TextModal.route(event.interaction)
    else:
        logging.info("unhandled event", event)


if __name__ == "__main__":
    logging.debug("\n\n\n")
    bot.run()
