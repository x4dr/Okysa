from asyncio import sleep
from pathlib import Path

import hikari
import songbird
from hikari import VoiceError
from songbird import ffmpeg, TrackError
from songbird.hikari import Voicebox

from Golconda.Rights import owner_only

playing: list[songbird.TrackHandle] = []


async def check_playing(handle: songbird.TrackHandle, voice: Voicebox):
    while True:
        try:
            print((await handle.get_info()).play_time)
            await sleep(1)
        except TrackError:
            await voice.disconnect()
            break


async def restream():
    for handle in playing:
        handle.stop()
        handle.play()


async def stop_stream(bot: hikari.GatewayBot, gid: hikari.Snowflake):
    await bot.voice.disconnect(gid)


# noinspection PyUnusedLocal
@owner_only
async def stream_sound(
    author: hikari.User,
    bot: hikari.GatewayBot,
    gid: hikari.Snowflake,
    user: hikari.Snowflake,
):
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
    i = await handle.get_info()


# await check_playing(handle, voice)
