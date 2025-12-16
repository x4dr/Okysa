import logging
import urllib.parse

import discord
from discord import app_commands
from gamepack.Dice import DescriptiveError
from gamepack.MDPack import MDObj
from gamepack.WikiPage import WikiPage


from Golconda.Tools import who_am_i

logger = logging.getLogger(__name__)

NESTEDDICT = dict[str, "NESTEDDICT"]


def dict_search(wanted_key, tree: NESTEDDICT, path=tuple()):
    if isinstance(tree, list):
        for idx, el in enumerate(tree):
            yield from dict_search(wanted_key, el, path + (idx,))
    elif isinstance(tree, dict):
        for k in tree:
            if k == wanted_key:
                yield path + (k,)
        # you can add order of width-search by sorting result of tree.items()
        for k, v in tree.items():
            yield from dict_search(wanted_key, v, path + (k,))


def table_render(node: MDObj):
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

    def __init__(self):
        super().__init__(timeout=None)
        self.embed = None
        self.message = ""

    @classmethod
    def make_from(cls, path: str, storage):
        wiki = cls()
        path: [str] = [x for x in path.split(":") if x]
        page = WikiPage.load_locate(path[0])
        wikimd = page.md()
        newmd = wikimd
        for step in path[1:]:
            newmd = newmd.children[step]
            if newmd is None:
                raise DescriptiveError(
                    f"invalid step in path: {step}, options were :{', '.join(wikimd.children.keys())}"
                )
            wikimd = newmd
        embed = discord.Embed(
            title="->".join(path),
            description=(wikimd.plaintext.strip().removeprefix("[TOC]").strip())[:4000],
            url="https://"
            + storage.nossilink
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
            b = discord.ui.Select(custom_id=f"{Wiki.prefix}subheadings")
            b.callback = nav_callback
            for sub in list(wikimd.children.keys())[:25]:
                b.add_option(label=sub, value=f"{':'.join(path + [sub])}")
            wiki.add_item(b)
        edit_button = discord.ui.Button(label="Edit", custom_id=":".join(path))
        edit_button.callback = edit_callback
        wiki.add_item(edit_button)
        if len(wikimd.children) > 25:
            embed.set_footer(
                text="Tags: "
                + " ".join(page.tags)
                + "\n"
                + f"More than 25 subheadings, <{len(wikimd.children) - 25}> have been ommitted"
            )
        else:
            embed.set_footer(text="Tags: " + " ".join(page.tags) + "\n")
        wiki.embed = embed
        wiki.message = ("```" + message + "```") if message else ""
        return wiki


class EditModal(discord.ui.Modal):
    def __init__(self, path):
        path = path.split(":")
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

    async def on_submit(self, interaction: discord.Interaction):
        storage = interaction.client.storage
        proper_path = WikiPage.locate(self.path[0])
        page = WikiPage.load(proper_path)
        md = page.md()

        new_text = self.text_input.value
        if len(self.path) > 1:
            md.replace_content_by_path(self.path[1:], new_text)
        else:
            md = MDObj.from_md(new_text)
        page.body = md.to_md()
        # noinspection PyBroadException

        try:
            author_storage = storage.storage.get(str(interaction.user.id))
            user = who_am_i(author_storage, storage)
        except DescriptiveError as e:
            await interaction.channel.send_message(e.args[0])
        except Exception:
            # noinspection PyUnresolvedReferences
            await interaction.response.defer()
        else:
            # noinspection PyUnresolvedReferences
            await interaction.response.defer()
            page.save(
                interaction.client.user.name,
                proper_path,
                user + " via discord",
            )
            WikiPage.cacheclear(proper_path)
            wiki = Wiki.make_from(":".join(self.path), storage)
            await interaction.message.edit(
                embed=wiki.embed, view=wiki, content=wiki.message
            )


async def nav_callback(
    interaction: discord.Interaction,
):
    storage = interaction.client.storage
    if "values" in interaction.data:
        path = interaction.data["values"][0]
    else:
        path = interaction.data["custom_id"][len(Wiki.prefix) :]
    wiki = Wiki.make_from(path, storage)
    await interaction.message.edit(embed=wiki.embed, view=wiki, content=wiki.message)
    # noinspection PyUnresolvedReferences
    await interaction.response.defer()


async def edit_callback(interaction: discord.Interaction):
    # noinspection PyUnresolvedReferences
    await interaction.response.send_modal(EditModal(interaction.data["custom_id"]))


def register(tree: discord.app_commands.CommandTree):
    @app_commands.describe(
        site="the thing in the url after /wiki/", path="the path of headlines to follow"
    )
    @tree.command(name="wiki", description="Accesses the Nosferatu net wiki")
    async def wiki(interaction: discord.Interaction, site: str, path: str = ""):
        storage = interaction.client.storage
        try:
            view = Wiki.make_from(f"{site}:{path}", storage)
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message("", embed=view.embed, view=view)
        except DescriptiveError as e:
            # noinspection PyUnresolvedReferences
            return await interaction.response.send_message(f"{e}", ephemeral=True)
