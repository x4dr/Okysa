import asyncio
import logging
from typing import Callable, TypeVar, ParamSpec, Concatenate, Coroutine, Awaitable
import hikari
from Pantheon.Ateph import get_storage

T = TypeVar("T")
P = ParamSpec("P")

logger = logging.getLogger(__name__)


async def allowed(msg: hikari.Message):
    storage = get_storage()
    dmchannel = isinstance(msg.channel_id, hikari.DMChannel)
    mentioned = storage.me in msg.mentions.users if storage.me else False
    adressed = msg.content.strip().lower().startswith(storage.me.username.lower())
    allowed_in_channel = msg.channel_id in storage.allowed_channels
    return dmchannel or mentioned or adressed or allowed_in_channel


def is_owner(u: hikari.User):
    return get_storage().app.owner == u


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
