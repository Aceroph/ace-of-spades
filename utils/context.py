from discord.ext import commands
from typing import Optional
import discord


class Context(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def reply(self, **kwargs):
        if self.interaction.response.is_done():
            return await self.interaction.followup.send(**kwargs)
        else:
            return await self.reply(**kwargs)
