from typing import Type

import lavaplayer

from Golconda.Slash import Slash
from Golconda.Storage import evilsingleton


async def start(lavalink: lavaplayer.LavalinkClient, guild_id: int, what: str):
    tracks = await lavalink.get_tracks(what)
    for track in tracks:
        print(track)
        await lavalink.play(guild_id, track=track)
        break
    else:
        print("not found")


def register(slash: Type[Slash]):
    @slash.owner()
    @slash.cmd("sync", "closes and reopens the pipe to sync")
    async def restream(cmd: slash):
        await evilsingleton().lavalink.stop(cmd.guild_id)
        await evilsingleton().lavalink.stop(cmd.guild_id)
        await cmd.respond_instant_ephemeral("Ok")

    @slash.owner()
    @slash.cmd("stop", "stops the music")
    async def stop(cmd: Slash):
        await evilsingleton().lavalink.stop(cmd.guild_id)
        await cmd.respond_instant_ephemeral("stopped")

    @slash.owner()
    @slash.cmd("end", "leaves")
    async def leave(cmd: Slash):
        await evilsingleton().bot.voice.disconnect(cmd.guild_id)
        await cmd.respond_instant_ephemeral("ended")

    @slash.owner()
    @slash.option("what", "what to play")
    @slash.cmd("play", "play whatever")
    async def play(cmd: Slash):
        await start(evilsingleton().lavalink, cmd.guild_id, cmd.get("what"))
        await cmd.respond_instant_ephemeral("lets go")

    # noinspection PyUnusedLocal
    @slash.owner()
    @slash.cmd("stream", "opens the sound stream directly from the NossiNetNode")
    async def stream_sound(cmd: slash):
        bot = evilsingleton().bot
        lavalink = evilsingleton().lavalink
        states = bot.cache.get_voice_states_view_for_guild(cmd.guild_id)
        voice_state = [
            state
            async for state in states.iterator().filter(
                lambda i: i.user_id == cmd.author.id
            )
        ]
        channel_id = voice_state[0].channel_id
        await bot.update_voice_state(cmd.guild_id, channel_id)
        await lavalink.wait_for_connection(cmd.guild_id)
        await cmd.respond_instant_ephemeral(f"Joined <#{channel_id}>")
        """handle = await voice.play_source(
            await ffmpeg(
                str(Path("~/soundpipe").expanduser()),
                pre_input_args="-f s32le -ac 2 -ar 48000",
                args="-f s16le -ac 2 -ar 48000 -acodec pcm_f32le -",
            )
        )
        playing.append(handle)"""
