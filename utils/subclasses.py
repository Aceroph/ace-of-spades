from discord.ext import commands
from . import subclasses, misc
from cogs import errors
import traceback
import discord
import time


class Cog(commands.Cog):
    def __init__(self):
        self.emoji: str = "<:sadcowboy:1002608868360208565>"
        self.time: float = time.time()


class View(discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_quit(self, author: discord.User, row: int = None):
        self.author = author
        button = discord.ui.Button(style=discord.ButtonStyle.red, label="Quit", row=row)
        button.callback = self.quit_callback
        return self.add_item(button)

    async def quit_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            raise errors.NotYourButton

        await interaction.message.delete()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        if isinstance(error, errors.NotYourButton):
            return await interaction.response.send_message(
                error.reason or "This is not your button !", ephemeral=True
            )

        # UNHANDLED ERRORS BELLOW
        # Process the traceback to clean path !
        trace = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        embed = discord.Embed(
            title=f":warning: Unhandled error in item : {item.type}",
            description=f"```py\n{misc.clean_traceback(trace)}```",
            color=discord.Color.red(),
        )
        embed.set_footer(
            text=f"Caused by {interaction.user.display_name} in {interaction.guild.name if interaction.guild else 'DMs'} ({interaction.guild.id if interaction.guild else 0})",
            icon_url=interaction.user.avatar.url,
        )

        view = subclasses.View()
        view.add_quit(interaction.user)

        # Owner embed w full traceback
        await interaction.client.get_user(interaction.client.owner_id).send(embed=embed)

        # User error
        embed = discord.Embed(
            title=f":warning: {type(error).__qualname__}",
            description=f"> {' '.join(error.args)}" if len(error.args) > 0 else None,
            color=discord.Color.red(),
        )
        return await interaction.response.send_message(embed=embed, view=view)

    async def on_timeout(self):
        self.clear_items()


class Paginator:
    def __init__(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
        max_lines: int = 25,
        prefix: str = None,
        suffix: str = None,
    ) -> None:
        self.embed = embed
        self.index: int = 0
        self.max_lines = max_lines
        self.ctx = ctx

        self.pages = []
        self.current_page = []

        self.prefix = prefix + "\n" if prefix else ""
        self.suffix = suffix if suffix else ""

        # Buttons
        self.view = View()

    def add_line(self, line: str = "") -> None:
        self.current_page.append(line)

        if len(self.current_page) == self.max_lines - 1:
            self.pages.append(self.prefix + "\n".join(self.current_page) + self.suffix)
            self.current_page = []

    def add_page(self, page: str) -> None:
        self.pages.append(self.prefix + page + self.suffix)

    async def start(self):
        self.embed.description = self.pages[self.index]
        self.update_buttons(self.ctx.author)
        self.embed.set_footer(text=f"Page {self.index+1} of {len(self.pages)}")
        await self.ctx.reply(embed=self.embed, view=self.view, mention_author=False)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise errors.NotYourButton

        self.index += 1
        return await self.update_page(interaction)

    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise errors.NotYourButton

        self.index -= 1
        return await self.update_page(interaction)

    async def first_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise errors.NotYourButton

        self.index = 0
        return await self.update_page(interaction)

    async def last_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise errors.NotYourButton

        self.index = len(self.pages) - 1
        return await self.update_page(interaction)

    def update_buttons(self, user: discord.User):
        # Update buttons
        self.view.clear_items()

        _first = discord.ui.Button(
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}",
            disabled=self.index == 0,
        )
        _first.callback = self.first_page
        self.view.add_item(_first)

        _previous = discord.ui.Button(
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}", disabled=self.index == 0
        )
        _previous.callback = self.previous_page
        self.view.add_item(_previous)

        self.view.add_quit(user)

        _next = discord.ui.Button(
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}",
            disabled=self.index + 1 == len(self.pages),
        )
        _next.callback = self.next_page
        self.view.add_item(_next)

        _last = discord.ui.Button(
            emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}",
            disabled=self.index + 1 == len(self.pages),
        )
        _last.callback = self.last_page
        self.view.add_item(_last)

    async def update_page(self, interaction: discord.Interaction):
        self.update_buttons(interaction.user)

        page = self.pages[self.index]
        embed = interaction.message.embeds[0]
        embed.description = page
        embed.set_footer(text=f"Page {self.index+1} of {len(self.pages)}")
        return await interaction.response.edit_message(embed=embed, view=self.view)
