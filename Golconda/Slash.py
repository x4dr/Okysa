import logging
import re
from asyncio import sleep
from typing import Callable, Awaitable, AsyncGenerator, Type, Iterable

import hikari
from hikari.api import RESTClient

from Golconda.Rights import is_owner

Slash_Command_Type = Callable[["Slash"], Awaitable[None]]
Slash_Decorator_Type = Callable[[Slash_Command_Type], Slash_Command_Type]
commandname = re.compile(r"^[\w-]{1,32}$")


class Slash:
    _commands = {}
    _buttons = {}

    def __init__(self, command: hikari.CommandInteraction):
        self._cmd = command
        self.author = command.user
        self.guild_id = command.guild_id
        self.channel_id = command.channel_id
        self.app = command.app

    def get(self, name, default=None):
        return next((c.value for c in self._cmd.options if c.name == name), default)

    async def fetch_channel(self) -> hikari.TextableChannel:
        return await self._cmd.fetch_channel()

    async def respond_instant(self, content, /, **kwargs):
        await self._cmd.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            content,
            **kwargs,
        )

    async def change_response(self, **kwargs):
        return await self._cmd.edit_initial_response(**kwargs)

    async def respond_instant_ephemeral(self, content, **kwargs):
        kwargs.setdefault("flags", hikari.MessageFlag.NONE)
        kwargs["flags"] |= hikari.MessageFlag.EPHEMERAL
        return await self.respond_instant(content, **kwargs)

    async def respond_later(self, work: AsyncGenerator[dict, None], **kwargs):
        kwargs.setdefault("content", "loading...")
        await self._cmd.create_initial_response(
            hikari.ResponseType.DEFERRED_MESSAGE_CREATE,
            **kwargs,
        )
        try:
            async for step in work:
                n = kwargs.copy()
                n.update(step)
                await self._cmd.edit_initial_response(
                    **n,
                )
        except Exception as e:

            await self._cmd.edit_initial_response(content=f"Error: {e}")
            await sleep(2)
            await self._cmd.delete_initial_response()
            raise

    @classmethod
    def owner(cls) -> Slash_Decorator_Type:
        def wrapper(func: Slash_Command_Type) -> Slash_Command_Type:
            async def replacement(cmd: Slash):
                if is_owner(cmd.author):
                    return await func(cmd)
                else:
                    await cmd.respond_instant_ephemeral(
                        "Error: This command is owner only."
                    )

            return replacement

        return wrapper

    @classmethod
    def cmd(cls, name: str, desc: str) -> Slash_Decorator_Type:
        if not commandname.match(name):
            raise ValueError(f"'{name}' is not valid")

        def wrapper(func: Slash_Command_Type) -> Slash_Command_Type:
            cls._commands[name] = {"cmd": func, "desc": desc, "options": []}
            func.slashname = name
            print(f"registering {func.__name__} with {name}")
            return func

        return wrapper

    @classmethod
    def sub(
        cls,
        name: str,
        desc: str,
        of: Slash_Command_Type,
        group=False,
        choices=None,
    ):
        if not commandname.match(name):
            raise ValueError(f"'{name}' is not valid")

        def wrapper(func: Slash_Command_Type):
            if hasattr(of, "slashname"):
                destination = cls._commands[of.slashname]["options"]
                if hasattr(of, "groupname"):
                    if group:
                        raise ValueError("cannot nest groups")
                    func.groupname = of.groupname
                    destination = next(x for x in destination if x.name == of.groupname)

                destination.append(
                    hikari.CommandOption(
                        type=hikari.OptionType.SUB_COMMAND_GROUP
                        if group
                        else hikari.OptionType.SUB_COMMAND,
                        name=name,
                        description=desc,
                        choices=choices,
                    )
                )
                func.slashname = of.slashname
                if group:
                    func.groupname = name
                else:
                    func.subname = name
                if hasattr(of, "sub"):
                    of.sub[name] = func
                else:
                    of.sub = {name: func}
                return func
            raise ValueError(f"{of.__name__} is not a group or slash command!")

        return wrapper

    @classmethod
    def option(
        cls,
        name: str,
        desc: str,
        t: hikari.OptionType = hikari.OptionType.STRING,
        required=True,
        choices=None,
    ):
        if not commandname.match(name) or len(desc) not in range(1, 100):
            raise ValueError(f"'{name}', '{desc}' invalid")

        def wrapper(func: Slash_Command_Type):
            if hasattr(func, "slashname"):
                destination = cls._commands[func.slashname]["options"]
                if hasattr(func, "groupname"):
                    destination = next(
                        x for x in destination if x.name == func.groupname
                    ).options
                if hasattr(func, "subname"):
                    destination = next(x for x in destination if x.name == func.subname)
                    if not destination.options:
                        destination.options = []  # make sure there is a list
                    destination = destination.options
                destination.append(
                    hikari.CommandOption(
                        type=t,
                        name=name,
                        description=desc,
                        is_required=required,
                        choices=choices,
                    )
                )
                return func
            raise ValueError(f"{func.__name__} is not a slash command!")

        return wrapper

    @classmethod
    def all(cls, rest: RESTClient):
        for i, (name, conf) in enumerate(cls._commands.items()):
            logging.info(f"registering {name} {i+1}/{len(cls._commands)}")
            c = rest.slash_command_builder(name, conf["desc"])
            for o in conf["options"]:
                c.add_option(o)
            yield c

    @classmethod
    async def route(cls, cmd: hikari.CommandInteraction):
        c = cls._commands.get(cmd.command_name, None)
        if c:
            c = c["cmd"]
            await c(cls(cmd))
            while sub := next((x for x in cmd.options or [] if x.type <= 2), None):
                cmd.options = sub.options
                await c.sub[sub.name](cls(cmd))

    @classmethod
    def register(cls, registers: Iterable[Callable[[Type["Slash"]], None]]):
        for f in registers:
            f(cls)

    @classmethod
    def interact(cls, interaction: hikari.ComponentInteraction):
        pass
