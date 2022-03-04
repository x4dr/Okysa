import asyncio
import logging
from typing import Callable, TypeVar, ParamSpec, Awaitable

import hikari

from Golconda.Storage import getstorage, Storage

T = TypeVar("T")
P = ParamSpec("P")

logger = logging.getLogger(__name__)
s: Storage | None = None


def storage():
    global s
    try:
        s = getstorage()
        return s
    except Exception:
        return None


async def allowed(msg: hikari.PartialMessage):
    if not (storage()):  # uninitialized
        return False
    dmchannel = isinstance(msg.channel_id, hikari.DMChannel)
    mentioned = s.me in msg.mentions.users if s.me and msg.mentions else False
    adressed = msg.content and msg.content.strip().lower().startswith(
        s.me.username.lower()
    )
    allowed_in_channel = msg.channel_id in s.allowed_channels
    return dmchannel or mentioned or adressed or allowed_in_channel


def is_owner(u: hikari.User):
    return s.app.owner == u


def owner_only(f: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    def inner(calling_user: hikari.User, *args, **kwargs):
        if is_owner(calling_user):
            kwargs["user"] = kwargs.get("user") or calling_user.id
            # replace user arg by calling user only if it's not given, that way, admin can call for another
            return f(calling_user, *args, **kwargs)
        else:
            logger.info(f"tried to access {f.__name__} as {calling_user.username}")
            return asyncio.gather([])

    return inner
