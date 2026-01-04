import asyncio
import os
import discord


def soundpipe():
    # #!/bin/bash
    # pacat -r -d alsa_output.[input] \
    # --format=s16le --rate=48000 -ac 2 > ~/soundpipe
    os.system("setup_soundpipe")
    return discord.FFmpegPCMAudio(
        os.path.expanduser("~/soundpipe"),
        before_options="-f s16le -ar 48000 -ac 2",
    )


def register(tree: discord.app_commands.CommandTree):
    @tree.command(name="stream")
    async def stream(interaction: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await interaction.response.send_message("Connecting...")
        connection: discord.VoiceClient = await interaction.user.voice.channel.connect()
        try:
            connection.play(soundpipe())
            while connection.is_playing():
                await asyncio.sleep(5)
        finally:
            await connection.disconnect()
            await interaction.delete_original_response()
