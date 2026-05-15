import asyncio
from typing import Callable, Any, Awaitable

functions: list[tuple[Callable[..., Awaitable[float]], list[Any]]] = []


def call_periodically(
    func: Callable[..., Awaitable[float]],
) -> Callable[..., Awaitable[float]]:
    functions.append((func, []))
    return func


def call_periodically_with(
    func: Callable[..., Awaitable[float]], args: list[Any]
) -> None:
    functions.append((func, args))


async def periodic() -> None:
    while True:
        next_run = 15.0
        for func, args in functions:
            try:
                res = await func(*args)
                next_run = min(next_run, float(res))
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    f"Error in periodic function {func.__name__}"
                )
        await asyncio.sleep(max(next_run, 1.0))
