from cogs.errors import NotYourButton
from discord.ext import commands
from .subclasses import View
import discord


class Paginator:
    def __init__(
        self,
        ctx: commands.Context,
        embed: discord.Embed = None,
        max_lines: int = None,
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
        if self.max_lines:
            self.current_page.append(line)

            if len(self.current_page) == self.max_lines - 1:
                self.add_page("\n".join(self.current_page))
        else:
            if len("\n".join(self.current_page)) + len(line) >= 2000:
                self.add_page()
                self.current_page.append(line)
            else:
                self.current_page.append(line)

            if len("\n".join(self.current_page)) == 2000:
                self.add_page()

    def add_page(self, page: str = None) -> None:
        self.pages.append(
            self.prefix + (page or "\n".join(self.current_page)) + self.suffix
        )
        self.current_page = []

    async def start(self):
        self.update_buttons(self.ctx.author)
        self.add_page()

        if self.embed:
            self.embed.description = self.pages[self.index]
            self.embed.set_footer(text=f"Page {self.index+1} of {len(self.pages)}")
            return await self.ctx.reply(
                embed=self.embed, view=self.view, mention_author=False
            )
        else:
            return await self.ctx.reply(
                self.pages[self.index], view=self.view, mention_author=False
            )

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise NotYourButton

        self.index += 1
        return await self.update_page(interaction)

    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise NotYourButton

        self.index -= 1
        return await self.update_page(interaction)

    async def first_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise NotYourButton

        self.index = 0
        return await self.update_page(interaction)

    async def last_page(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            raise NotYourButton

        self.index = len(self.pages) - 1
        return await self.update_page(interaction)

    def update_buttons(self, user: discord.User):
        # Update buttons
        self.view.clear_items()

        _first = discord.ui.Button(
            label="<<",
            disabled=self.index == 0,
        )
        _first.callback = self.first_page
        self.view.add_item(_first)

        _previous = discord.ui.Button(label="<", disabled=self.index == 0)
        _previous.callback = self.previous_page
        self.view.add_item(_previous)

        self.view.add_quit(user, self.ctx.guild)

        _next = discord.ui.Button(
            label=">",
            disabled=self.index + 1 == len(self.pages),
        )
        _next.callback = self.next_page
        self.view.add_item(_next)

        _last = discord.ui.Button(
            label=">>",
            disabled=self.index + 1 == len(self.pages),
        )
        _last.callback = self.last_page
        self.view.add_item(_last)

    async def update_page(self, interaction: discord.Interaction):
        self.update_buttons(interaction.user)

        if self.embed:
            embed = interaction.message.embeds[0]
            embed.description = self.pages[self.index]
            embed.set_footer(text=f"Page {self.index+1} of {len(self.pages)}")
            return await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            return await interaction.response.edit_message(
                self.pages[self.index], view=self.view
            )
