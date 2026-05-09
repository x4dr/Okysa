import re
from typing import Generator, Any

import discord
from discord import app_commands

from Golconda import Rights
from Golconda.RollInterface import get_lastrolls_for
from Golconda.Storage import evilsingleton

discordid = re.compile(r"<@!(\d+)>")


class BaseCommand:
    """Core bot utilities and account management.

    Commands:
    - whoami: Get your registered account.
    - register <account>: Link your account.
    - anon <message>: Send an anonymous message.
    - list: Show your last 10 rolls.
    - invoke: Make the bot listen here.
    - banish: Make the bot stop listening here.
    - die: Terminate the bot (Owner only).
    - make bridge: Setup channel bridge (Owner only).
    - def <name>=<roll>: Define a macro.
    - undef <name>: Remove a macro.
    """

    @staticmethod
    async def handle(ctx, args: list[str]) -> None:
        if not args:
            return

        cmd = args[0].lower()
        match cmd:
            case "whoami":
                res = await BaseCommand.whoami_logic(str(ctx.author.id))
                await ctx.reply(res)
            case "register":
                if len(args) < 2:
                    # Routing's help_system should handle this now
                    return
                else:
                    res = await BaseCommand.register_logic(
                        str(ctx.author.id), ctx.author.name, args[1]
                    )
                    await ctx.reply(res)
            case "anon":
                if len(args) < 2:
                    await ctx.reply("Usage: anon <message>")
                else:
                    # Agnostic anon: just sending back what was said for now
                    # as per anon_logic's simple implementation.
                    res = await BaseCommand.anon_logic(
                        str(ctx.channel.id), " ".join(args[1:])
                    )
                    await ctx.reply(res)
            case "list":
                res = await BaseCommand.list_rolls_logic(ctx.author.mention)
                await ctx.reply(res)
            case "invoke":
                # Moving invoke/banish here for consistency
                from Commands.Base import invoke

                await invoke(ctx.message)
            case "banish":
                from Commands.Base import banish

                await banish(ctx.message)
            case "die":
                if ctx.is_owner():
                    await ctx.message.add_reaction("\U0001f480")
                    s = evilsingleton()
                    if hasattr(s, "client") and s.client:
                        await s.client.close()
            case "make":
                if len(args) > 1 and args[1].lower() == "bridge":
                    from Commands.Base import make_bridge

                    if not await make_bridge(ctx.message):
                        await ctx.reply("nope!")
            case "def":
                from Golconda.Routing import define

                s = evilsingleton()
                await define(
                    " ".join(args[1:]),
                    ctx.message,
                    s.storage.setdefault(str(ctx.author.id), {}),
                )
                s.write()
            case "undef":
                from Golconda.Routing import undefine

                s = evilsingleton()
                await undefine(
                    " ".join(args[1:]),
                    ctx.message.add_reaction,
                    s.storage.setdefault(str(ctx.author.id), {}),
                )
                s.write()

    @staticmethod
    async def whoami_logic(user_id: str) -> str:
        storage = evilsingleton().storage
        try:
            acc = storage[str(user_id)]["NossiAccount"]
            data = storage[str(user_id)]
            return f"You are {acc} \nYour data is: {data}."
        except KeyError:
            return "You are not registered."

    @staticmethod
    async def register_logic(user_id: str, user_name: str, nossiaccount: str) -> str:
        s = evilsingleton()
        d: dict[str, str | dict] = s.storage.setdefault(str(user_id), {"defines": {}})
        if not nossiaccount:
            d.pop("NossiAccount", None)
            return "... Who are you?"
        else:
            d["NossiAccount"] = nossiaccount.upper()
            d["DiscordAccount"] = str(user_id)
            s.save_conf(
                str(d["NossiAccount"]),
                "unconfirmed_discord_link",
                f"{user_id}({user_name})",
            )
            s.write()
            return (
                f"I have saved your account as {d['NossiAccount']}.\n"
                f"go to https://{s.nossilink}/config/unconfirmed_discord_link to confirm it"
            )

    @staticmethod
    async def anon_logic(channel_id: str, say: str) -> str:
        # This one is tricky as it needs to send a message to a channel.
        # Agnostic logic usually returns 'instructions' for the harness.
        return f"anon: {say}"

    @staticmethod
    async def list_rolls_logic(mention: str) -> str:
        roll_list = get_lastrolls_for(mention)
        if not roll_list:
            return "No rolls found."
        msg = ""
        for i, roll in enumerate(roll_list):
            msg += f"{len(roll_list) - i}: {roll[0]} -> {roll[1].r}\n"
        return msg


async def invoke(message: Any) -> None:
    storage = evilsingleton()
    if str(message.channel.id) not in storage.allowed_channels:
        storage.allowed_channels.append(str(message.channel.id))
        storage.write()
        await message.reply("i will now listen here, until someone banishes me.")
    await message.add_reaction("\N{THUMBS UP SIGN}")


async def banish(message: Any) -> None:
    storage = evilsingleton()
    if str(message.channel.id) in storage.allowed_channels:
        storage.allowed_channels.remove(str(message.channel.id))
        storage.write()
    await message.add_reaction("\N{THUMBS UP SIGN}")


def message_prep(message: str) -> Generator[list[str], None, None]:
    storage = evilsingleton()
    me = storage.me
    selfname = me.name.lower() if me else "okysa"
    for msg in (message or "").split("\n"):
        msg = msg.strip("` ")
        if msg.lower().startswith(selfname):
            msg = msg[len(selfname) :]
        res = []
        tokens = msg.split()
        is_def = tokens and tokens[0].lower() == "def"
        for x in tokens:
            if is_def and "=" in x:
                res.extend([p for p in x.partition("=") if p])
            else:
                res.append(x)
        yield res


async def make_bridge(message: Any) -> bool:
    if Rights.is_owner(message.author):
        storage = evilsingleton()
        storage.bridge_channel = str(message.channel.id)
        storage.save_conf("bridge", "channelid", str(message.channel.id))
        if hasattr(message.channel, "create_webhook"):
            storage.save_conf(
                "bridge",
                "webhook",
                (await message.channel.create_webhook(name="NosferatuBridge")).url,
            )
        storage.write()
        await message.add_reaction("\N{LINK SYMBOL}")
        return True
    return False


def register(tree: discord.app_commands.CommandTree) -> None:
    @tree.command(
        name="whoami",
        description="gets the currently configured NosferatuNetwork account name",
    )
    async def who_am_i(interaction: discord.Interaction) -> None:
        res = await BaseCommand.whoami_logic(str(interaction.user.id))
        await interaction.response.send_message(res, ephemeral=True)

    @app_commands.describe(say="the message that will be posted")
    @tree.command(name="anon", description="say something anonymously")
    async def anon(interaction: discord.Interaction, say: str) -> None:
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("message sent", ephemeral=True)
        if interaction.channel:
            res = await BaseCommand.anon_logic(str(interaction.channel.id), say)
            await interaction.channel.send(res)

    @tree.command(name="list", description="lists the last rolls and results")
    async def rolllist(interaction: discord.Interaction) -> None:
        res = await BaseCommand.list_rolls_logic(interaction.user.mention)
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message(res, ephemeral=True)

    @app_commands.describe(nossiaccount="your name on the NosferatuNet")
    @tree.command(
        name="register", description="sets up the connection to the NosferatuNetwork"
    )
    async def i_am(interaction: discord.Interaction, nossiaccount: str) -> None:
        res = await BaseCommand.register_logic(
            str(interaction.user.id), interaction.user.name, nossiaccount
        )
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message(res, ephemeral=True)
