import logging

import discord

from Golconda.Storage import Storage

logger = logging.getLogger(__name__)


async def allowed(msg: discord.Message) -> bool:
    storage: Storage = msg.client.storage
    if not storage:  # uninitialized
        return False
    if msg.channel.id in storage.allowed_channels:
        return True
    if not msg.guild:  # no guild === being in a dm
        return True
    if msg.mentions and storage.me in msg.mentions:
        return True
    if msg.role_mentions and any(
        r.id in msg.role_mentions for r in storage.getroles(msg.guild)
    ):
        return True
    return (msg.content or "").strip().lower().startswith(storage.me.name.lower())


def is_owner(u: discord.User, client: discord.Client | None = None):
    # try to get client from user if not provided, though typically not available on User
    c = client
    if not c:
        # Fallback if user is actually a Member which has client? No, Member has guild
        # Use a passed client
        logger.warning(f"is_owner called without client for {u}")
        return False
    return c.application.owner == u
