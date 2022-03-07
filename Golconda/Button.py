from collections.abc import Awaitable
from typing import Callable, Coroutine, Protocol

import hikari.api


class ButtonFunc(Protocol):
    def add_to(self, row: hikari.api.ActionRowBuilder, name, param="") -> None:
        """A Button func can add itself to an actionrowbuilder,
        with its display name and parameter (no underscores!)"""


class Button:
    _buttons = {}

    @classmethod
    async def route(cls, event: hikari.ComponentInteraction):
        print(f"{event.custom_id=}")
        name, param = event.custom_id.rsplit("_", 1)
        f = cls._buttons[name](event, param)
        if isinstance(f, Awaitable):
            f = await f
        await event.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        return f

    @staticmethod
    def add_to_adder(func) -> ButtonFunc:
        def add_to(row: hikari.api.ActionRowBuilder, name, param=""):
            if "_" in param:
                raise ValueError("param name cannot have _")
            return (
                row.add_button(1, f"{func.__name__}_{param}")
                .set_label(name)
                .add_to_container()
            )

        if not hasattr(func, "add_to"):
            func.add_to = add_to
        return func

    def __new__(
        cls, func: Callable[[hikari.ComponentInteraction, str], Coroutine]
    ) -> ButtonFunc:
        cls._buttons[func.__name__] = func
        return cls.add_to_adder(func)
