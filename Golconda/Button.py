from collections.abc import Awaitable
from typing import Callable, Coroutine, Protocol

import hikari.api


class ButtonFunc(Protocol):
    def add_to(self, row: hikari.api.MessageActionRowBuilder, name, param="") -> None:
        """A Button func can add itself to an MessageActionRowBuilder,
        with its display name and parameter (no underscores!)"""

    def as_select_menu(
        self, description: str, options: [(str, str)]
    ) -> hikari.impl.MessageActionRowBuilder:
        """A Button func can also handle being an entire action row"""


class Button:
    _buttons = {}

    @classmethod
    async def route(cls, event: hikari.ComponentInteraction):
        match event.component_type:
            case hikari.ComponentType.BUTTON:
                name, param = event.custom_id.rsplit("_", 1)
                f = cls._buttons[name](event, param)
            case hikari.ComponentType.SELECT_MENU:
                name, param = event.custom_id, ":".join(event.values)
                f = cls._buttons[name](event, param)
            case _:
                raise Exception(event)
        if isinstance(f, Awaitable):
            f = await f
        try:
            await event.create_initial_response(
                hikari.ResponseType.DEFERRED_MESSAGE_UPDATE
            )
        except hikari.errors.BadRequestError:
            pass
        return f

    @staticmethod
    def add_to_adder(func) -> ButtonFunc:
        def add_to(row: hikari.api.MessageActionRowBuilder, name, param=""):
            if "_" in param:
                raise ValueError("param name cannot have _")
            return (
                row.add_button(1, f"{func.__name__}_{param}")
                .set_label(name)
                .add_to_container()
            )

        def as_select_menu(
            description: str, options: list[str, str]
        ) -> hikari.impl.MessageActionRowBuilder:
            row = hikari.impl.MessageActionRowBuilder()
            sel = row.add_select_menu(func.__name__).set_placeholder(description)
            for desc, privid in options:
                sel.add_option(desc, privid).add_to_menu()
            sel.add_to_container()
            return row

        if not hasattr(func, "add_to"):
            func.add_to = add_to
            func.as_select_menu = as_select_menu
        return func

    def __new__(
        cls, func: Callable[[hikari.ComponentInteraction, str], Coroutine]
    ) -> ButtonFunc:
        cls._buttons[func.__name__] = func
        return cls.add_to_adder(func)
