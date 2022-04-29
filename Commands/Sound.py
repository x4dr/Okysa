from typing import Type

import hikari
import lavaplayer

from Golconda.Slash import Slash
from Golconda.Storage import evilsingleton


async def start(lavalink: lavaplayer.LavalinkClient, guild_id: int, what: str):
    tracks = await lavalink.get_tracks(what)
    for track in tracks:
        print(track)
        return await lavalink.play(guild_id, track=track)
    else:
        print("not found")


def register(slash: Type[Slash]):
    @slash.owner()
    @slash.cmd("stop", "stops the music")
    async def stop(cmd: Slash):
        await evilsingleton().lavalink.stop(cmd.guild_id)
        await cmd.respond_instant_ephemeral("stopped")

    @slash.owner()
    @slash.option("value", "1-100", hikari.OptionType.INTEGER)
    @slash.cmd("volume", "sets the volume")
    async def vol(cmd: Slash):
        await evilsingleton().lavalink.volume(cmd.guild_id, volume=cmd.get("value"))
        await cmd.respond_instant_ephemeral("yup")

    @slash.owner()
    @slash.cmd("end", "leaves")
    async def leave(cmd: Slash):
        await cmd.respond_instant_ephemeral(f"ending {cmd.guild_id=}")
        await evilsingleton().bot.update_voice_state(cmd.guild_id, None)  # disconnect

    @slash.owner()
    @slash.option("what", "what to play")
    @slash.cmd("play", "play whatever")
    async def play(cmd: Slash):
        await start(evilsingleton().lavalink, cmd.guild_id, cmd.get("what"))
        await cmd.respond_instant_ephemeral("lets go")

    @slash.option("where", "with : for minutes, without : for seconds")
    @slash.cmd("skip", "time control")
    async def skip(cmd: Slash):
        timecode = cmd.get("where")
        lavalink = evilsingleton().lavalink
        await cmd.respond_instant_ephemeral("y")
        q = await lavalink.queue(cmd.guild_id)
        if not q:
            return
        try:
            timesplits = reversed(timecode.split(":", 2))
            pos = sum(int(timepart) * 60**i for i, timepart in enumerate(timesplits))
        except ValueError:
            return
        await lavalink.seek(cmd.guild_id, pos * 1000)

    # noinspection PyUnusedLocal
    @slash.owner()
    @slash.option("what", "starts playing immediately", required=False)
    @slash.cmd("stream", "opens the sound stream directly from the NossiNetNode")
    async def stream_sound(cmd: slash):
        bot = evilsingleton().bot
        lavalink = evilsingleton().lavalink
        lavalink.connect()
        states = bot.cache.get_voice_states_view_for_guild(cmd.guild_id)
        voice_state = [
            state
            async for state in states.iterator().filter(
                lambda i: i.user_id == cmd.author.id
            )
        ]
        channel_id = voice_state[0].channel_id
        await bot.update_voice_state(cmd.guild_id, channel_id)
        connection = await lavalink.wait_for_connection(cmd.guild_id)
        await cmd.respond_instant_ephemeral(f"Joined <#{channel_id}> {connection}")
        if what := cmd.get("what"):
            if what == "test":
                what = "https://www.youtube.com/watch?v=jlB_tmbiqbM"
            await start(evilsingleton().lavalink, cmd.guild_id, what)
        """handle = await voice.play_source(
            await ffmpeg(
                str(Path("~/soundpipe").expanduser()),
                pre_input_args="-f s32le -ac 2 -ar 48000",
                args="-f s16le -ac 2 -ar 48000 -acodec pcm_f32le -",
            )
        )
        playing.append(handle)"""
