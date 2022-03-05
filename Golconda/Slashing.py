from typing import Coroutine, Callable, Awaitable, Iterable, AsyncGenerator

import hikari
from hikari.api import RESTClient

from Golconda.Rights import is_owner

Slash_Command_Type = Callable[["Slash"], Awaitable[None]]
Slash_Decorator_Type = Callable[[Slash_Command_Type], Slash_Command_Type]


class Slash:
    _commands = {}

    def __init__(self, command: hikari.CommandInteraction):
        self._cmd = command

    @property
    def user(self):
        return self._cmd.user

    def get(self, name, default=None):
        return next((c for c in self._cmd.options if c.name == name), default)

    async def fetch_channel(self) -> hikari.TextableChannel:
        return await self._cmd.fetch_channel()

    async def respond_instant(self, content, /, **kwargs):
        await self._cmd.create_initial_response(
            hikari.CommandResponseTypesT.MESSAGE_CREATE,
            content,
            **kwargs,
        )

    async def respond_instant_ephemeral(self, content, **kwargs):
        kwargs.setdefault("tags", hikari.MessageFlag.NONE)
        kwargs["tags"] |= hikari.MessageFlag.EPHEMERAL
        return await self.respond_instant(content, **kwargs)

    async def respond_later(self, work: AsyncGenerator[dict], **kwargs):
        kwargs.setdefault("content", "loading...")
        await self._cmd.create_initial_response(
            hikari.CommandResponseTypesT.DEFERRED_MESSAGE_CREATE,
            **kwargs,
        )
        async for step in work:
            n = kwargs.copy()
            n.update(step)
            await self._cmd.edit_initial_response(
                **n,
            )

    @classmethod
    def owner(cls) -> Slash_Decorator_Type:
        def wrapper(func: Slash_Command_Type) -> Slash_Command_Type:
            async def replacement(cmd: Slash):
                if is_owner(cmd.user):
                    return await func(cmd)
                else:
                    await cmd.respond_instant_ephemeral(
                        "Error: This command is owner only."
                    )

            return replacement

        return wrapper

    @classmethod
    def cmd(cls, name: str, desc: str) -> Slash_Decorator_Type:
        def wrapper(func: Slash_Command_Type) -> Slash_Command_Type:
            cls._commands[name] = {"cmd": func, "desc": desc, "options": []}
            func.slashname = name
            return func

        return wrapper

    @classmethod
    def sub(
        cls,
        name: str,
        desc: str,
        of: Slash_Command_Type,
        group=False,
        required=True,
        choices=None,
    ):
        def wrapper(func: Slash_Command_Type):
            destination = None
            if hasattr(of, "slashname"):
                destination = cls._commands[of.slashname]["options"]
                if hasattr(of, "groupname"):
                    if group:
                        raise ValueError("cannot nest groups")
                    func.groupname = of.groupname
                    destination = cls._commands[of.slashname]["options"]
                if destination:
                    destination.append(
                        hikari.CommandOption(
                            type=hikari.OptionType.SUB_COMMAND_GROUP
                            if group
                            else hikari.OptionType.SUB_COMMAND,
                            name=name,
                            description=desc,
                            is_required=required,
                            choices=choices,
                        )
                    )
                    func.slashname = of.slashname
                    if group:
                        func.groupname = name
                    else:
                        func.subname = name
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
        def wrapper(func: Slash_Command_Type):
            if hasattr(func, "slashname"):
                destination = cls._commands[func.slashname]["options"]
                if hasattr(func, "groupname"):
                    destination = next(
                        x for x in destination if x.name == func.groupname
                    ).options
                if hasattr(func, "subname"):
                    destination = next(
                        x for x in destination if x.name == func.subname
                    ).options
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
        result = []
        for name, conf in cls._commands.items():
            c = rest.slash_command_builder(name, conf["desc"])
            for o in conf["options"]:
                c.add_option(o)
            result.append(c)
        return result

    @classmethod
    async def route(cls, cmd: hikari.CommandInteraction):
        c = cls._commands.get(cmd.command_name, None)
        if c:
            await c["cmd"](cls(cmd))
