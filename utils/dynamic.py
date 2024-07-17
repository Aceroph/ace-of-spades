# For all dynamic items
import re
from typing import Any, Coroutine, Union

import discord

from . import errors


class QuitButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"quit:user:(?P<user>[0-9]+):guild:(?P<guild>[0-9]+)",
):
    def __init__(
        self,
        *,
        author: Union[int, discord.abc.User],
        guild: Union[int, discord.Guild],
        label: str = "Close",
    ):
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.red,
                label=label,
                custom_id=f"quit:user:{getattr(author, 'id', author)}:guild:{getattr(guild, 'id', guild) or 0}",
            )
        )
        self.author = getattr(author, "id", author)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author and self.author:
            raise errors.NotYourButton

        await interaction.message.delete()  # type: ignore

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.DynamicItem,
        match: re.Match[str],
        /,
    ):
        return cls(author=int(match["user"]), guild=int(match["guild"]))
