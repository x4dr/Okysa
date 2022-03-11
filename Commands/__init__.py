from typing import Callable, Type, Iterable

from Golconda.Slash import Slash


def get_register_functions() -> Iterable[Callable[[Type[Slash]], None]]:
    from Commands.Oracle import register

    yield register
    from Commands.Base import register

    yield register
    from Commands.Minecraft import register

    yield register
    from Commands.Wiki import register

    yield register
    from Commands.Remind import register

    yield register
    from Commands.Char import register

    yield register
