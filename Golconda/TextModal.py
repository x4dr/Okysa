from asyncio import Protocol
from collections.abc import Awaitable

import hikari
from typing import Callable, Coroutine


class ModalFunc(Protocol):
    def get_modal(
        self, uid: str, label: str, text: str
    ) -> hikari.impl.TextInputBuilder:
        """A Modal func can return the correct Component that represents it"""

    def route(self):
        """get the route to this element"""


class TextModal:
    _modals = {}

    @classmethod
    async def route(cls, event: hikari.ModalInteraction):
        name = event.custom_id
        modal = event.components[0].components[0]
        f = cls._modals[name](event, modal)
        if isinstance(f, Awaitable):
            f = await f

        try:
            await event.create_initial_response(
                hikari.ResponseType.DEFERRED_MESSAGE_UPDATE
            )
        except hikari.errors.BadRequestError:
            pass
        return f

    @classmethod
    def representation_adder(cls, func):
        def representation(
            uid: str, label: str, text: str
        ) -> hikari.impl.TextInputBuilder:
            return (
                hikari.impl.TextInputBuilder(
                    label=label,
                    container=hikari.impl.ActionRowBuilder(),
                    custom_id=uid,
                )
                .set_style(hikari.TextInputStyle.PARAGRAPH)
                .set_value(text)
                .add_to_container()
            )

        def route():
            return func.__name__

        if not hasattr(func, "get_modal"):
            func.get_modal = representation
            func.route = route
        return func

    def __new__(
        cls, func: Callable[[hikari.ComponentInteraction, str], Coroutine]
    ) -> ModalFunc:
        cls._modals[func.__name__] = func
        return cls.representation_adder(func)
