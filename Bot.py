import logging
import os

import hikari

import Commands
from Golconda.Button import Button
from Golconda.Rights import allowed
from Golconda.Routing import main_route
from Golconda.Slash import Slash
from Golconda.Storage import setup

Slash.register(Commands.get_register_functions())

if os.name != "nt":
    import uvloop

    uvloop.install()

with open(os.path.expanduser("~/token.discord"), "r") as tokenfile:
    bot = hikari.GatewayBot(token=tokenfile.read().strip())


@bot.listen(hikari.StartedEvent)
async def startup(event: hikari.StartedEvent):
    print("STARTED")
    app = await event.app.rest.fetch_application()
    cmds = list(Slash.all(event.app.rest))[:]
    await event.app.rest.set_application_commands(app, cmds)
    await app.owner.send(
        "Hi :) \nGuilds im in: "
        + str(", ".join(x.name for x in bot.cache.get_guilds_view().values()))
    )
    logging.info(f"Owner is {app.owner}")
    await setup(bot)


@bot.listen()
async def on_edit(event: hikari.MessageUpdateEvent) -> None:
    if event.is_human and await allowed(event.message):
        await main_route(event)


@bot.listen()
async def on_message(event: hikari.MessageCreateEvent) -> None:
    """Listen for messages being created."""
    if event.is_human and await allowed(event.message):
        print("routing", event.message.content)
        await main_route(event)


# @bot.listen(hikari.VoiceEvent)
# async def on_voice_event(event: hikari.VoiceEvent)


@bot.listen(hikari.InteractionCreateEvent)
async def on_interaction_create(event: hikari.InteractionCreateEvent):
    if isinstance(event.interaction, hikari.ComponentInteraction):
        return await Button.route(event.interaction)
    if isinstance(event.interaction, hikari.CommandInteraction):
        return await Slash.route(event.interaction)
    print(f"interaction received:{event}, {event.interaction.type}")


if __name__ == "__main__":
    print("starting...")
    bot.run()
