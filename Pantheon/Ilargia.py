import asyncio
import os


if os.name != "nt":
    import uvloop
    uvloop.install()

functions = []
period = 15


def call_periodically(func):
    functions.append((func, []))
    return func


def call_periodically_with(func, args):
    functions.append((func, args))


async def periodic():
    loop = asyncio.get_running_loop()
    t = 0
    while True:
        remove = []
        for func, args in functions:
            if func(*args):
                remove.append(func)
        for func in remove:
            functions.remove(func)
        now = loop.time()
        t += ((now - t) // period + 1) * period
        await asyncio.sleep(t - now)


asyncio.run(periodic())
