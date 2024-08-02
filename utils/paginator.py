from copy import copy
from typing import Optional

import discord
from discord.ext import commands

from . import errors, misc


class Paginator(discord.ui.View):
    def __init__(
        self,
        ctx: commands.Context,
        embed: discord.Embed = None,
        subtitle: str = misc.space,
        max_lines: int = 2048,
        prefix: str = "",
        suffix: str = "",
        timeout: Optional[float] = 180.0,
    ) -> None:
        super().__init__(timeout=timeout)

        self.embed = embed
        self.index: int = 0
        self.max_lines = max_lines
        self.ctx = ctx
        self.author = ctx.author

        self.pages: list[str] = []
        self.current_page: list[str] = []

        self.subtitle = subtitle
        self.prefix = prefix
        self.suffix = suffix

        self.quit_button.label = f"Quit • Page 1/{len(self.pages)}"

    async def interaction_check(
        self, interaction: discord.Interaction[discord.Client]
    ) -> bool:
        if interaction.user != self.author:
            raise errors.NotYourButton
        return True

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

    def add_page(self, page: str | None = None) -> None:
        self.pages.append(
            self.prefix + (page or "\n".join(self.current_page)) + self.suffix
        )
        self.current_page = []

    async def start(
        self,
        destination: Optional[discord.abc.Messageable] = None,
    ):
        self.add_page()
        self._update_buttons()

        if destination:
            respond = destination.send
            if isinstance(destination, discord.abc.User):
                self.author = destination
        else:
            respond = self.ctx.reply

        if self.embed:
            embed = copy(self.embed)
            await respond(
                embed=self._update_embed(embed), view=self, mention_author=False
            )
        else:
            await respond(self.pages[self.index], view=self, mention_author=False)

    @discord.ui.button(label="<<", disabled=True)
    async def first_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.index = 0
        await self.update_page(interaction)

    @discord.ui.button(label="<", disabled=True)
    async def previous_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.index -= 1
        await self.update_page(interaction)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.danger)
    async def quit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        reference = interaction.message.reference
        if reference:
            try:
                msg = await interaction.channel.fetch_message(reference.message_id)    # type: ignore
                await msg.delete()
            except:
                pass

        await interaction.message.delete()  # type: ignore
        self.stop()

    @discord.ui.button(label=">")
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.index += 1
        await self.update_page(interaction)

    @discord.ui.button(label=">>")
    async def last_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.index = len(self.pages) - 1
        await self.update_page(interaction)

    def _update_buttons(self):
        """Method to disable/enable buttons and update the page count"""
        self.first_page.disabled = self.previous_page.disabled = (
            self.index == 0
        )  # disabled first two button when first page is open
        self.last_page.disabled = self.next_page.disabled = (
            self.index == len(self.pages) - 1
        )  # disable last two button if last page is open

        self.quit_button.label = f"Quit • Page {self.index+1}/{len(self.pages)}"  # update page count on quit button

    async def update_page(self, interaction: discord.Interaction) -> None:
        self._update_buttons()
        assert interaction.message is not None
        if self.embed:
            embed = interaction.message.embeds[0]    
            await interaction.response.edit_message(
                embed=self._update_embed(embed), view=self
            )
        else:
            await interaction.response.edit_message(
                content=self.pages[self.index], view=self
            )
