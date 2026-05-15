import logging
from typing import Callable, TypeVar, ParamSpec, Awaitable, Optional

from gamepack.Dice import DescriptiveError

from Golconda.Storage import evilsingleton, Storage

T = TypeVar("T")
P = ParamSpec("P")

logger = logging.getLogger(__name__)
s: Optional[Storage] = None


def storage():
    global s
    try:
        s = evilsingleton()
        return s
    except DescriptiveError:
        return None


def allowed(msg) -> bool:
    if not (storage()):
        return False

    if str(msg.channel.id) in s.allowed_channels:
        return True

    if not msg.guild_id:
        return True

    if any(str(u.id) == str(s.me.id) for u in msg.mentions):
        return True

    if msg.role_mentions and hasattr(s, "getroles"):
        roles = s.getroles(msg.guild_id)
        if roles and any(
            str(r.id) in (str(rm) for rm in msg.role_mentions) for r in roles
        ):
            return True

    return (msg.content or "").strip().lower().startswith(str(s.me.name).lower())


def is_owner(u) -> bool:
    import os

    matrix_owner = os.getenv("MATRIX_OWNER")
    if matrix_owner and str(u.id) == matrix_owner:
        return True

    if s and hasattr(s, "owner_id") and s.owner_id:
        return str(u.id) == str(s.owner_id)

    if s and s.me and str(u.id) == str(s.me.id):
        return True

    return False


def owner_only(f: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T | None]]:
    async def inner(calling_user, *args, **kwargs):
        if is_owner(calling_user):
            kwargs["user"] = kwargs.get("user") or calling_user.id
            return await f(calling_user, *args, **kwargs)
        else:
            logger.info(f"tried to access {f.__name__} as {calling_user.name}")
            return None

    return inner
