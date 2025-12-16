import subprocess

import discord
from discord import app_commands


def register(tree: discord.app_commands.CommandTree):
    # noinspection PyUnusedLocal
    group = app_commands.Group(name="minecraftserver", description="Minecraft control")

    @group.command(name="up", description="brings the server up")
    async def mcup(interaction: discord.Interaction):
        storage = interaction.client.storage
        if interaction.user.id in storage.storage.get("mc_powerusers", []):
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("Starting Server...")
            subprocess.call(["mcstart"])
        else:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("Access Denied!", ephemeral=True)

    @app_commands.describe(person="mention")
    @group.command(name="reg", description="(un)register a new authorized user")
    async def register_user(
        interaction: discord.Interaction, person: discord.User = None
    ):
        if interaction.user == interaction.guild.owner:
            s = interaction.client.storage
            registered = s.storage.get("mc_powerusers", [])
            if person in registered:
                registered.remove(person)
                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"Removed {person} from allowed users.", ephemeral=True
                )
            else:
                registered.append(person)
                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"Added {person} to allowed users.", ephemeral=True
                )
            s.storage["mc_powerusers"] = registered
            s.write()
        else:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("Access Denied!", ephemeral=True)

    tree.add_command(group)
