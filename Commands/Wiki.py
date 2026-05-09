import logging
import urllib.parse
from typing import Generator, Tuple

import discord
from discord import app_commands
from gamepack.Dice import DescriptiveError
from gamepack.MDPack import MDObj
from gamepack.WikiPage import WikiPage

from Golconda.Storage import evilsingleton
from Golconda.Tools import who_am_i

logger = logging.getLogger(__name__)


class WikiCommand:
    """Accesses the Nosferatu net wiki.

    Commands:
    - wiki <site> [path]: View a wiki page or subheading.

    Example: wiki charactersheet
    """

    @staticmethod
    async def handle(ctx, args: list[str]) -> None:
        if len(args) < 2:
            return

        subcommand = args[1].lower()
        # In text mode, 'wiki site:path' or 'wiki site path'
        path_str = subcommand
        if len(args) > 2:
            path_str = f"{subcommand}:{' '.join(args[2:])}"

        try:
            title, description, url, content, children, tags = (
                await WikiCommand.get_page_logic(path_str)
            )
            res = f"**{title}**\n{description}\n"
            if content:
                res += f"```\n{content}\n```\n"
            res += f"Link: {url}\n"
            if children:
                res += f"Subheadings: {', '.join(children)}\n"
            await ctx.reply(res)
        except Exception as e:
            await ctx.reply(f"Wiki error: {e}")

    @staticmethod
    async def get_page_logic(
        path_str: str,
    ) -> Tuple[str, str, str, str, list[str], list[str]]:
        """View a wiki page or subheading.
        Usage: wiki <site> [path]
        - <site>: The thing in the URL after /wiki/
        - [path]: The path of headlines to follow (colon-separated).
        """
        path: list[str] = [x for x in path_str.split(":") if x]
        page = WikiPage.load_locate(path[0])
        wikimd = page.md()

        for step in path[1:]:
            newmd = wikimd.children.get(step)
            if newmd is None:
                options = ", ".join(list(wikimd.children.keys()))
                raise DescriptiveError(
                    f"invalid step in path: {step}, options were :{options}"
                )
            wikimd = newmd

        title = "->".join(path)
        description = (wikimd.plaintext.strip().removeprefix("[TOC]").strip())[:4000]
        url = (
            "https://"
            + evilsingleton().nossilink
            + "/wiki/"
            + urllib.parse.quote(f"{path[0]}")
            + "#"
            + urllib.parse.quote(f"{path[-1].lower() if len(path) > 1 else ''}")
        )

        # We return the components to build the embed/view
        content = table_render(wikimd)
        return title, description, url, content, list(wikimd.children.keys()), page.tags

    @staticmethod
    async def save_page_logic(path_str: str, new_text: str, user_id: str) -> str:
        path = path_str.split(":")
        proper_path = WikiPage.locate(path[0])
        page = WikiPage.load(proper_path)
        md = page.md()

        if len(path) > 1:
            md.replace_content_by_path(path[1:], new_text)
        else:
            md = MDObj.from_md(new_text)
        page.body = md.to_md()

        author_storage = evilsingleton().storage.get(str(user_id))
        if not author_storage:
            raise DescriptiveError("You are not registered.")
        user = who_am_i(author_storage)
        if not user:
            raise DescriptiveError("You are not registered.")

        page.save("Okysa", proper_path, user + " via agnostic-frontend")
        WikiPage.reload_cache(proper_path)
        return "Saved successfully."


def dict_search(target: str, tree: dict | list) -> Generator[Tuple, None, None]:
    if isinstance(tree, dict):
        for k, v in tree.items():
            if k == target:
                yield (k,)
            if isinstance(v, (dict, list)):
                for res in dict_search(target, v):
                    yield (k,) + res
    elif isinstance(tree, list):
        for i, v in enumerate(tree):
            if isinstance(v, (dict, list)):
                for res in dict_search(target, v):
                    yield (i,) + res


def table_render(node: MDObj) -> str:
    result = ""
    for table in node.tables:
        widths = [len(x) for x in table.headers]
        for r in table.rows:
            for i, cell in enumerate(r):
                widths[i] = max(widths[i], len(cell))
        formatted_headers = " ".join(
            header.center(widths[i]) for i, header in enumerate(table.headers)
        )
        formatted_rows = "\n".join(
            " ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
            for row in table.rows
        )
        result += f"{formatted_headers}\n{formatted_rows}\n\n"
    return result


class Wiki(discord.ui.View):
    prefix = "wiki:"

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.embed: discord.Embed | None = None
        self.message: str = ""

    @classmethod
    def make_from(cls, path_str: str) -> "Wiki":
        # Note: Wrap the async call if needed, but here it's easier to keep the old load logic or refactor carefully.
        # Original logic remains mostly same but could use WikiLogic
        wiki = cls()
        path: list[str] = [x for x in path_str.split(":") if x]
        page = WikiPage.load_locate(path[0])
        wikimd = page.md()
        for step in path[1:]:
            newmd = wikimd.children.get(step)
            if newmd is None:
                options = ", ".join(list(wikimd.children.keys()))
                raise DescriptiveError(
                    f"invalid step in path: {step}, options were :{options}"
                )
            wikimd = newmd
        embed = discord.Embed(
            title="->".join(path),
            description=(wikimd.plaintext.strip().removeprefix("[TOC]").strip())[:4000],
            url="https://"
            + evilsingleton().nossilink
            + "/wiki/"
            + urllib.parse.quote(f"{path[0]}")
            + "#"
            + urllib.parse.quote(f"{path[-1].lower() if len(path) > 1 else ''}"),
            color=0x05F012,
        )
        message = table_render(wikimd)
        if len(path) > 1:
            b = discord.ui.Button(
                label="⬆️",
                custom_id=f"{cls.prefix}{':'.join(path[:-1])}",
                style=discord.ButtonStyle.primary,
            )
            b.callback = nav_callback
            wiki.add_item(b)
        if len(wikimd.children) < 5:
            for sub in wikimd.children:
                b = discord.ui.Button(
                    label=sub,
                    custom_id=f"{cls.prefix}{':'.join(path + [sub])}",
                    style=discord.ButtonStyle.primary,
                )
                b.callback = nav_callback
                wiki.add_item(b)
        else:
            sel = discord.ui.Select(custom_id=f"{Wiki.prefix}subheadings")
            sel.callback = nav_callback
            for sub in list(wikimd.children.keys())[:25]:
                sel.add_option(label=sub, value=f"{':'.join(path + [sub])}")
            wiki.add_item(sel)
        edit_button = discord.ui.Button(label="Edit", custom_id=":".join(path))
        edit_button.callback = edit_callback
        wiki.add_item(edit_button)
        embed.set_footer(text="Tags: " + " ".join(page.tags) + "\n")
        wiki.embed = embed
        wiki.message = ("```" + message + "```") if message else ""
        return wiki


class EditModal(discord.ui.Modal):
    def __init__(self, path_str: str) -> None:
        path = path_str.split(":")
        self.path = path
        page = WikiPage.load_locate(path[0])
        super().__init__(title="Edit " + (page.title if page.title else path[0]))
        self.original_message = page.md().get_content_by_path(self.path[1:]).to_md()
        self.text_input = discord.ui.TextInput(
            label="Enter new text",
            style=discord.TextStyle.paragraph,
            default=self.original_message[:4000],
            required=True,
            max_length=4000,
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await WikiCommand.save_page_logic(
                ":".join(self.path), self.text_input.value, str(interaction.user.id)
            )
            if not interaction.response.is_done():
                await interaction.response.defer()
            wiki = Wiki.make_from(":".join(self.path))
            if interaction.message:
                await interaction.message.edit(
                    embed=wiki.embed, view=wiki, content=wiki.message
                )
        except DescriptiveError as e:
            await interaction.response.send_message(e.args[0], ephemeral=True)


async def nav_callback(interaction: discord.Interaction) -> None:
    if interaction.data and "values" in interaction.data:
        path = interaction.data["values"][0]
    elif interaction.data and "custom_id" in interaction.data:
        path = interaction.data["custom_id"][len(Wiki.prefix) :]
    else:
        return
    wiki = Wiki.make_from(path)
    if interaction.message:
        await interaction.message.edit(
            embed=wiki.embed, view=wiki, content=wiki.message
        )
    await interaction.response.defer()


async def edit_callback(interaction: discord.Interaction) -> None:
    if interaction.data and "custom_id" in interaction.data:
        await interaction.response.send_modal(EditModal(interaction.data["custom_id"]))


def register(tree: discord.app_commands.CommandTree) -> None:
    @app_commands.describe(
        site="the thing in the url after /wiki/", path="the path of headlines to follow"
    )
    @tree.command(name="wiki", description="Accesses the Nosferatu net wiki")
    async def wiki(interaction: discord.Interaction, site: str, path: str = "") -> None:
        try:
            view = Wiki.make_from(f"{site}:{path}")
            await interaction.response.send_message("", embed=view.embed, view=view)
        except DescriptiveError as e:
            await interaction.response.send_message(f"{e}", ephemeral=True)
