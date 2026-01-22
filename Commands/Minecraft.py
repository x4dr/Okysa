import subprocess

import discord
from discord import app_commands

from Golconda.Storage import evilsingleton


def register(tree: discord.app_commands.CommandTree) -> None:
    # noinspection PyUnusedLocal
    group = app_commands.Group(name="minecraftserver", description="Minecraft control")

    @group.command(name="up", description="brings the server up")
    async def mcup(interaction: discord.Interaction) -> None:
        if interaction.user.id in evilsingleton().storage.get("mc_powerusers", []):
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("Starting Server...")
            subprocess.call(["mcstart"])
        else:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("Access Denied!", ephemeral=True)

    @app_commands.describe(person="mention")
    @group.command(name="reg", description="(un)register a new authorized user")
    async def register_user(
        interaction: discord.Interaction, person: discord.User | None = None
    ) -> None:
        if person is None:
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                "Please provide a user.", ephemeral=True
            )
            return

        if interaction.guild and interaction.user == interaction.guild.owner:
            s = evilsingleton()
            registered = s.storage.get("mc_powerusers", [])
            if person.id in registered:
                registered.remove(person.id)
                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"Removed {person} from allowed users.", ephemeral=True
                )
            else:
                registered.append(person.id)
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
