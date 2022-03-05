import logging
import os
import hikari
from hikari import MessageFlag

from Golconda.Rights import allowed
from Golconda.Routing import main_route
from Golconda.Slashing import slash_commands, slash_route
from Golconda.Storage import setup

if os.name != "nt":
    import uvloop

    uvloop.install()

with open(os.path.expanduser("~/token.discord"), "r") as tokenfile:
    bot = hikari.GatewayBot(token=tokenfile.read().strip())


@bot.listen(hikari.StartedEvent)
async def startup(event: hikari.StartedEvent):
    print("STARTED")
    app = await event.app.rest.fetch_application()
    await event.app.rest.set_application_commands(app, slash_commands(event.app.rest))
    print(await app.app.rest.fetch_application_commands(app))

    await app.owner.send(
        "Hi :) \nGuilds im in: "
        + str(", ".join(x.name for x in bot.cache.get_guilds_view().values()))
    )
    logging.info(f"Owner is {app.owner}")
    await setup(bot)


@bot.listen()
async def on_edit(event: hikari.MessageUpdateEvent) -> None:
    if event.is_human or not allowed(event.message):
        await main_route(event)


@bot.listen()
async def on_message(event: hikari.MessageCreateEvent) -> None:
    """Listen for messages being created."""
    if event.is_human or await allowed(event.message):
        await main_route(event)


@bot.listen(hikari.InteractionCreateEvent)
async def on_interaction_create(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.CommandInteraction):
        print(f"interaction received:{event}, {event.interaction.type}")
        return
    cmd: hikari.CommandInteraction = event.interaction

    await slash_route(cmd)



if __name__ == "__main__":
    print("starting...")
    bot.run()
