import logging
from typing import Callable, TypeVar, ParamSpec, Awaitable

import discord
from gamepack.Dice import DescriptiveError

from Golconda.Storage import evilsingleton, Storage

T = TypeVar("T")
P = ParamSpec("P")

logger = logging.getLogger(__name__)
s: Storage | None = None


def storage():
    global s
    try:
        s = evilsingleton()
        return s
    except DescriptiveError:
        return None


async def allowed(msg: discord.Message) -> bool:
    if not (storage()):  # uninitialized
        return False
    if msg.channel.id in s.allowed_channels:
        return True
    if not msg.guild:  # no guild === being in a dm
        return True
    if msg.mentions and s.me in msg.mentions:
        return True
    if msg.role_mentions and any(
        r.id in msg.role_mentions for r in s.getrole(msg.guild)
    ):
        return True
    return (msg.content or "").strip().lower().startswith(s.me.name.lower())


def is_owner(u: discord.User):
    return s.client.application.owner == u


def owner_only(f: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    def inner(calling_user: discord.User, *args, **kwargs):
        if is_owner(calling_user):
            kwargs["user"] = kwargs.get("user") or calling_user.id
            # replace user arg by calling user only if it's not given, that way, admin can call for another
            return f(calling_user, *args, **kwargs)
        else:
            logger.info(f"tried to access {f.__name__} as {calling_user.name}")

            # noinspection PyUnusedLocal
            async def dummy(*a, **b):
                ...  # swallow invalid call

            return dummy

    return inner
