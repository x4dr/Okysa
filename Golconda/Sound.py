from asyncio import sleep
from pathlib import Path
from typing import cast

import hikari
import songbird
from hikari import VoiceError
from songbird import ffmpeg, TrackError
from songbird.hikari import Voicebox

from Golconda.Slash import Slash

playing: list[songbird.TrackHandle] = []


async def check_playing(handle: songbird.TrackHandle, voice: Voicebox):
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
    bot = cast(cmd.app, hikari.GatewayBot)  # we are in a GatewayBot
    gid = cmd.guild_id
    user = cmd.author
    vstate = bot.cache.get_voice_state(gid, user)
    if not vstate:
        return None
    try:
        voice = await Voicebox.connect(bot, gid, vstate.channel_id)
    except VoiceError:
        await bot.voice.disconnect(gid)
        voice = await Voicebox.connect(bot, gid, vstate.channel_id)

    handle = await voice.play_source(
        await ffmpeg(
            str(Path("~/soundpipe").expanduser()),
            pre_input_args="-f s32le -ac 2 -ar 48000",
            args="-f s16le -ac 2 -ar 48000 -acodec pcm_f32le -",
        )
    )
    playing.append(handle)


# await check_playing(handle, voice)
