"""
from asyncio import sleep
from pathlib import Path
from typing import cast

import hikari

from hikari import VoiceError

import lavalink

from Golconda.Slash import Slash
from Golconda.Storage import getstorage

playing: dict[int, lavalink.Client] = {}

async def check_playing(handle: TrackHandle, voice: Voicebox):
    while True:
        try:
            print((await handle.get_info()).play_time)
            await sleep(1)
        except TrackError:
            await voice.disconnect()
            break


@Slash.owner()
@Slash.cmd("sync", "closes and reopens the pipe to sync")
async def restream(cmd: Slash):
    for handle in playing:
        handle.stop()
        handle.play()
    await cmd.respond_instant_ephemeral("Ok")


async def stop_stream(bot: hikari.GatewayBot, gid: hikari.Snowflake):
    await bot.voice.disconnect(gid)


# noinspection PyUnusedLocal
@Slash.owner()
@Slash.cmd("stream", "opens the sound stream directly from the NossiNetNode")
async def stream_sound(cmd: Slash):
    lava = getstorage().lavalink
    pman: lavalink.PlayerManager = lava.player_manager.create(guild_id=cmd.guild_id)
    bot: hikari.GatewayBot = cast(cmd.app, hikari.GatewayBot)  # we are in a GatewayBot
    gid = cmd.guild_id
    user = cmd.author
    vstate: hikari.VoiceState = bot.cache.get_voice_state(gid, user)
    if not vstate:
        return None
    try:
        # ?? how do i connect
        # songbird voice = await Voicebox.connect(bot, gid, vstate.channel_id)
    except VoiceError:
        # await bot.voice.disconnect(gid)
        # voice = await Voicebox.connect(bot, gid, vstate.channel_id)
    # ?? how do i play
    handle = await voice.play_source(
        await ffmpeg(
            str(Path("~/soundpipe").expanduser()),
            pre_input_args="-f s32le -ac 2 -ar 48000",
            args="-f s16le -ac 2 -ar 48000 -acodec pcm_f32le -",
        )
    )
    playing.append(handle)


# await check_playing(handle, voice)
"""
