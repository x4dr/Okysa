import asyncio

functions = []


def call_periodically(func):
    functions.append((func, []))
    return func


def call_periodically_with(func, args):
    functions.append((func, args))


async def periodic():
    while True:
        next_run = 15
        for func, args in functions:
            next_run = min(next_run, await func(*args))
        await asyncio.sleep(next_run)
