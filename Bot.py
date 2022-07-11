import logging
import os
from datetime import datetime

import hikari

import Commands
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
    print(event)
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
    else:
        print(event)


if __name__ == "__main__":
    bot.run()
