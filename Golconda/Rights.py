import logging
from typing import Callable, TypeVar, ParamSpec, Awaitable

import hikari
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


async def allowed(msg: hikari.PartialMessage) -> bool:
    if not (storage()):  # uninitialized
        return False
    if msg.channel_id in s.allowed_channels:
        return True
    if msg.guild_id is None:  # no guild_id === being in a dm
        return True
    if msg.user_mentions_ids and s.me.id in msg.user_mentions_ids():
        return True
    if msg.mentions.role_ids and any(
        r.id in msg.mentions.role_ids for r in s.getrole(msg.guild_id)
    ):
        return True
    return msg.content.strip().lower().startswith(s.me.username.lower())


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

            # noinspection PyUnusedLocal
            async def dummy(*a, **b):
                ...  # swallow invalid call

            return dummy

    return inner
