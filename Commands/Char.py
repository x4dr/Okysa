import logging
from typing import List, Self, Mapping, Tuple

import discord
from discord import app_commands
from gamepack.FenCharacter import FenCharacter
from gamepack.WikiCharacterSheet import WikiCharacterSheet

from Golconda.CharacterService import who_am_i, get_discord_user_char
from Golconda.Storage import evilsingleton

logger = logging.getLogger(__name__)


class CharCommand:
    """View and manage your character data.

    Commands:
    - char [name]: View your own or another character's sheet.
    - xp <skill> [amount]: Add/remove XP or view current XP for a skill.

    Tip: Use ?char <command> for parameter details.
    """

    @staticmethod
    async def handle(ctx, args: list[str]) -> None:
        if len(args) < 2:
            # Default to showing own char
            name, data, url, text = await CharCommand.get_char_data(str(ctx.author.id))
            await ctx.reply(text)
            return

        subcommand = args[1].lower()
        if subcommand == "xp":
            if len(args) < 3:
                # Routing's help_system should handle this now
                return
            skill = args[2]
            amount = int(args[3]) if len(args) > 3 else 0
            res = await CharCommand.add_xp_logic(str(ctx.author.id), skill, amount)
            await ctx.reply(res)
        else:
            # Treat as char name (index 1)
            try:
                name, data, url, text = await CharCommand.get_char_data(args[1])
                await ctx.reply(text)
            except Exception as e:
                await ctx.reply(f"Error loading character '{args[1]}': {e}")

    @staticmethod
    async def get_char_data(
        access_id: str, path: list[str] = []
    ) -> Tuple[str, dict, str, str]:
        """View character sheets.
        Usage: char [name]
        - [name]: Optional. The name or ID of the character to view. If omitted, shows your linked character.
        """
        # Refactor part of Sheet.make_from logic here to be agnostic
        storage = evilsingleton()
        sheetlink = f"https://{storage.nossilink}/sheet/"

        c = access_id
        if access_id.isdigit():
            author_storage = storage.storage.get(str(access_id))
            if author_storage is None:
                raise ValueError("User not found in storage")
            user = who_am_i(author_storage)
            c = storage.load_conf(user, "character_sheet")
        elif access_id.startswith(sheetlink):
            c = access_id[len(sheetlink) :]

        wiki = WikiCharacterSheet.load_locate(c)
        chara = wiki.char
        name = chara.Character.get("Name", "Unnamed character")
        url = f"{sheetlink}{c}"

        # Return simplified data for text frontends
        res_text = f"**{name}**\nLink: {url}\n"
        if not path:
            for k, v in chara.Character.items():
                if k.lower() == "name":
                    continue
                res_text += f"{k}: {v}\n"
        elif path[0] == "categories":
            for k, v in chara.Categories.items():
                res_text += f"{k}\n"
        # ... more path handling could be added here for a full text UI

        return name, chara.Character, url, res_text

    @staticmethod
    async def add_xp_logic(user_id: str, skill: str, amount: int) -> str:
        """Add or remove experience points.
        Usage: xp <skill> <amount>
        - <skill>: The name of the skill (e.g., shooting, strength).
        - <amount>: Integer amount of XP to add (or negative to remove).
        """
        s = evilsingleton()
        author_storage = s.storage.get(str(user_id))
        if author_storage is None:
            return "You are not registered."
        user = who_am_i(author_storage)
        c = s.load_conf(user, "character_sheet")
        if not c:
            return "No character sheet linked."

        wiki = WikiCharacterSheet.load_locate(c)
        char: FenCharacter = wiki.char
        char.get_xp_for(skill)

        if not amount:
            return f"{skill} has {char.get_xp_for(skill)} xp."
        else:
            old = char.get_xp_for(skill)
            new = char.add_xp(skill, amount)
            me = s.me
            me_name = me.name if me else "Okysa"
            author = f"{user} via {me_name}"
            wiki.save(
                author,
                wiki.locate(c),
                f"{author} increased XP for {c}: {skill} from {old} to {new}\n",
            )
            return f"XP for {skill} increased from {old} to {new}."


class Sheet(discord.ui.View):
    prefix = "charsheet:"

    def __init__(self):
        super().__init__(timeout=None)
        self.embed = None
        self.storage = evilsingleton()
        self.sheetlink = f"https://{self.storage.nossilink}/sheet/"

    def make_from(self, access: str | int, path: list[str]) -> Self:
        if isinstance(access, int):
            author_storage = evilsingleton().storage.get(str(access))
            if author_storage is None:
                raise ValueError("User not found in storage")
            user = who_am_i(author_storage)
            c = evilsingleton().load_conf(user, "character_sheet")
        elif isinstance(access, str) and access.startswith(self.sheetlink):
            c = access[len(self.sheetlink) :]
        else:
            c = str(access)

        wiki = WikiCharacterSheet.load_locate(c)
        chara = wiki.char
        embed = discord.Embed(
            title=chara.Character.get("Name", "Unnamed character"),
            description="",
            url=f"{self.sheetlink}{c}",
            color=0x05F012,
        )

        self.add_nav_button("Character", "")
        self.add_nav_button("Categories", "categories")
        self.add_nav_button("Notes", "notes")
        self.add_nav_button("Experience", "experience")
        if not path:
            for i, (k, v) in enumerate(chara.Character.items()):
                if k.strip().lower() == "name":
                    continue
                if i > 25:
                    break
                embed.add_field(name=str(k), value=str(v) or "-", inline=True)
        elif path[0] == "categories":
            for i, (k, v) in enumerate(chara.Categories.items()):
                if k.strip().lower() == "name":
                    continue
                if i > 25:
                    break
                embed.add_field(name=str(k), value=categoryformat(v), inline=True)
            self.add_nav_select(
                "inspect",
                [
                    discord.SelectOption(label=x, value=x)
                    for x in chara.Categories.keys()
                ],
            )
        elif path[0] in chara.Categories:
            cat = chara.Categories[path[0]]
            left, right = "", ""
            dots = 5
            for h, section in cat.items():
                left += f"**_{h}_**\n"
                right += "_\n"
                for k, v in section.items():
                    left += f"{k}\n"
                    right += f"{maxdots(v, dots)}\n"
                dots = 3
            embed.add_field(name=path[0], value=left, inline=True)
            embed.add_field(name="༜", value=right, inline=True)
            self.add_nav_select(
                "inspect",
                [
                    discord.SelectOption(label=x, value=x)
                    for x in chara.Categories.keys()
                ],
            )
        elif path[0].lower() == "notes":
            embed.description = chara.Notes.originalMD[:4000]
        elif path[0].lower() in chara.experience_headings:
            xp = None
            for k, v in chara.Meta.items():
                if k.lower() in chara.experience_headings:
                    xp = v.tables
                    break
            if xp and xp[0]:
                left, right = "", ""
                for row in xp[0].rows:
                    left += f"**{row[0]}**\n"
                    right += maxdots(row[2], 5) + "\n"
                embed.add_field(name="Experience", value=left, inline=True)
                embed.add_field(name="༜", value=right, inline=True)
        self.embed = embed
        return self

    def add_nav_button(self, name, key):
        item = discord.ui.Button(
            label=name, custom_id=self.prefix + key, row=len(self.children) // 5
        )
        item.callback = nav_callback
        self.add_item(item)

    def add_nav_select(self, default, options: List[discord.SelectOption]):
        item = discord.ui.Select(custom_id=default, options=options)
        item.callback = nav_callback
        self.add_item(item)


async def nav_callback(interaction: discord.Interaction):
    if interaction.data is None or "custom_id" not in interaction.data:
        return
    custom_id = interaction.data.get("custom_id")
    if not isinstance(custom_id, str):
        return
    path_str = custom_id[len(Sheet.prefix) :]
    path = [x for x in path_str.split(":") if x]
    if interaction.message is None:
        return
    embed = interaction.message.embeds[0] if interaction.message.embeds else None
    if not embed or embed.url is None:
        return
    view = Sheet().make_from(embed.url, path)
    if view.embed:
        await interaction.message.edit(embed=view.embed, view=view)
    await interaction.response.defer()


def maxdots(v, maximum):
    try:
        return int(v) * "●" + "○" * (maximum - int(v))
    except ValueError, TypeError:
        return str(v)


def sectionformat(section: Mapping[str, str], maximum: int = 3) -> str:
    result = ""
    for k, v in section.items():
        result += f"**{k}**:\t{maxdots(v, maximum)}\n"
    return result


def categoryformat(category: Mapping[str, Mapping[str, str]]) -> str:
    sections = (x for x in list(category.values()))
    result = sectionformat(next(sections, {}), 5)
    linelen = len(result.split("\n")[-1])
    result += "_" * linelen + "\n"
    return result + sectionformat(next(sections, {}))


def register(tree: discord.app_commands.CommandTree):
    @tree.context_menu(name="Charactersheet")
    async def char_via_menu(interaction: discord.Interaction, user: discord.User):
        view = Sheet().make_from(user.id, [])
        if view.embed:
            await interaction.response.send_message("", embed=view.embed, view=view)

    @app_commands.describe(name="access a specific character")
    @tree.command(name="char")
    async def test(interaction: discord.Interaction, name: str | None = None):
        access: str | int = name or interaction.user.id
        view = Sheet().make_from(access, [])
        if view.embed:
            await interaction.response.send_message("", embed=view.embed, view=view)

    async def xp_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice]:
        try:
            char = get_discord_user_char(interaction.user)
        except KeyError:
            return []
        return [
            app_commands.Choice(name=x, value=x)
            for x in list(char.xp_cache.keys())
            if (x.strip()) and ((not current) or (current.lower() in x.lower()))
        ]

    @app_commands.describe(
        skill="the skill to add xp to", amount="the amount of xp to add"
    )
    @tree.command(name="xp", description="adds or removes xp from your character")
    @app_commands.autocomplete(skill=xp_autocomplete)
    async def xp(interaction: discord.Interaction, skill: str, amount: int):
        res = await CharCommand.add_xp_logic(str(interaction.user.id), skill, amount)
        await interaction.response.send_message(
            res, ephemeral=True if "not registered" in res else False
        )
