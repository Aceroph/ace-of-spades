from .errors import NotYourButton
from discord.ext import commands
from typing import Optional
from . import misc, errors
from copy import copy
import discord


class Paginator:
    def __init__(
        self,
        ctx: commands.Context,
        embed: discord.Embed = None,
        subtitle: str = misc.space,
        max_lines: int = 2048,
        prefix: str = "",
        suffix: str = "",
    ) -> None:
        self.embed = embed
        self.index: int = 0
        self.max_lines = max_lines
        self.ctx = ctx
        self.author = ctx.author

        self.pages = []
        self.current_page = []

        self.subtitle = subtitle
        self.prefix = prefix
        self.suffix = suffix

        # Buttons
        self.view = discord.ui.View()

    def _update_embed(self, embed: discord.Embed) -> discord.Embed:
        if self.embed.description:
            if getattr(self, "_added_field", False):
                embed.set_field_at(
                    index=len(embed.fields) - 1,
                    name=self.subtitle,
                    value=self.pages[self.index],
                )
            else:
                embed.add_field(name=self.subtitle, value=self.pages[self.index])
                self._added_field = True
        else:
            embed.description = self.pages[self.index]

        if self.embed.footer:
            embed.set_footer(
                text=f"{self.embed.footer.text} • Page {self.index+1} of {len(self.pages)}",
                icon_url=self.embed.footer.icon_url,
            )
        else:
            embed.set_footer(text=f"Page {self.index+1} of {len(self.pages)}")
        return embed

    def add_line(self, line: str = "") -> None:
        # Establish max
        if self.embed:
            if self.embed.description:
                MAX = 1024
            else:
                MAX = 2048
        else:
            MAX = 2000

        # If too many lines or too many characters, add page
        if (
            len("\n".join(self.current_page)) + len(line + self.prefix + self.suffix)
            > MAX - 1
            or len(self.current_page) + 1 > self.max_lines
        ):
            self.add_page("\n".join(self.current_page))

        self.current_page.append(line)

    def add_page(self, page: str = None) -> None:
        self.pages.append(
            self.prefix + (page or "\n".join(self.current_page)) + self.suffix
        )
        self.current_page = []

    async def start(
        self,
        destination: Optional[discord.abc.Messageable] = None,
    ):
        self.add_page()
        self.update_buttons(self.author)

        if destination:
            respond = destination.send
            if isinstance(destination, discord.abc.User):
                self.author = destination
        else:
            respond = self.ctx.reply

        if self.embed:
            embed = copy(self.embed)
            return await respond(
                embed=self._update_embed(embed), view=self.view, mention_author=False
            )
        else:
            return await respond(
                self.pages[self.index], view=self.view, mention_author=False
            )

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            raise NotYourButton

        self.index += 1
        return await self.update_page(interaction)

    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            raise NotYourButton

        self.index -= 1
        return await self.update_page(interaction)

    async def first_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            raise NotYourButton

        self.index = 0
        return await self.update_page(interaction)

    async def last_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            raise NotYourButton

        self.index = len(self.pages) - 1
        return await self.update_page(interaction)

    async def _quit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            raise errors.NotYourButton

        reference = interaction.message.reference
        if reference:
            try:
                msg = await interaction.channel.fetch_message(reference.message_id)
                await msg.delete()
            except:
                pass

        await interaction.message.delete()

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

        _quit = discord.ui.Button(label=f"Quit • Page {self.index+1}/{len(self.pages)}", style=discord.ButtonStyle.danger)
        _quit.callback = self._quit
        self.view.add_item(_quit)

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
            return await interaction.response.edit_message(
                embed=self._update_embed(embed), view=self.view
            )
        else:
            return await interaction.response.edit_message(
                content=self.pages[self.index], view=self.view
            )
