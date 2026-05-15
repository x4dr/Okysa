import subprocess
import discord
from discord import app_commands
from Golconda.Storage import evilsingleton


class MinecraftCommand:
    """Control the Minecraft server.

    Commands:
    - up: Brings the server up (Powerusers only).
    - reg <@user>: Toggle authorized users (Owner only).
    """

    @staticmethod
    async def handle(ctx, args: list[str]) -> None:
        if len(args) < 2:
            return

        subcommand = args[1].lower()
        match subcommand:
            case "up":
                res = await MinecraftCommand.up_logic(ctx)
                await ctx.reply(res)
            case "reg":
                target_id = int(args[2]) if len(args) > 2 else int(ctx.author.id)
                res = await MinecraftCommand.reg_logic(ctx, target_id, str(target_id))
                await ctx.reply(res)

    @staticmethod
    def _is_poweruser(user_id: int) -> bool:
        s = evilsingleton()
        registered = s.storage.get("mc_powerusers", [])
        return user_id in registered

    @staticmethod
    async def up_logic(ctx) -> str:
        """Brings the server up (Powerusers only).
        Usage: minecraft up
        """
        user_id = int(ctx.user.id) if hasattr(ctx, "user") else int(ctx.author.id)
        if MinecraftCommand._is_poweruser(user_id):
            subprocess.call(["mcstart"])
            return "Starting Server..."
        else:
            return "Access Denied!"

    @staticmethod
    async def reg_logic(ctx, target_id: int, target_name: str) -> str:
        """Toggle authorized users (Owner only).
        Usage: minecraft reg <@user>
        """
        if hasattr(ctx, "is_guild_owner"):
            if not ctx.is_guild_owner():
                return "Access Denied!"
        else:
            return "Access Denied!"

        s = evilsingleton()
        registered = s.storage.get("mc_powerusers", [])
        if target_id in registered:
            registered.remove(target_id)
            res = f"Removed {target_name} from allowed users."
        else:
            registered.append(target_id)
            res = f"Added {target_name} to allowed users."
        s.storage["mc_powerusers"] = registered
        s.write()
        return res


def register(tree: discord.app_commands.CommandTree) -> None:
    group = app_commands.Group(name="minecraftserver", description="Minecraft control")

    @group.command(name="up", description="brings the server up")
    async def mcup(interaction: discord.Interaction) -> None:
        res = await MinecraftCommand.up_logic(interaction)
        if res == "Access Denied!":
            await interaction.response.send_message(res, ephemeral=True)
        else:
            await interaction.response.send_message(res)

    @app_commands.describe(person="mention")
    @group.command(name="reg", description="(un)register a new authorized user")
    async def register_user(
        interaction: discord.Interaction, person: discord.User | None = None
    ) -> None:
        if person is None:
            await interaction.response.send_message(
                "Please provide a user.", ephemeral=True
            )
            return

        is_owner = interaction.guild and interaction.user == interaction.guild.owner
        if not is_owner:
            await interaction.response.send_message("Access Denied!", ephemeral=True)
            return

        s = evilsingleton()
        registered = s.storage.get("mc_powerusers", [])
        if person.id in registered:
            registered.remove(person.id)
            res = f"Removed {person} from allowed users."
        else:
            registered.append(person.id)
            res = f"Added {person} to allowed users."
        s.storage["mc_powerusers"] = registered
        s.write()
        await interaction.response.send_message(res, ephemeral=False)

    tree.add_command(group)
