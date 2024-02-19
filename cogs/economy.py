from utils import subclasses, sql_querries
from discord.ext import commands
from typing import Optional
from main import AceBot
import discord

class Economy(subclasses.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot: AceBot = bot
        self.emoji = '\N{COIN}'


    @commands.command()
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[int] = None):
        """Checks your current balance or another member's"""
        id = member.id if member else ctx.message.author.id
        
        current_balance = sql_querries.get_balance(self.bot.connection, id)
        if amount:
            if await self.bot.is_owner(ctx.message.author):
                sql_querries.set_balance(self.bot.connection, id, amount)
                await ctx.send(f"{abs(amount)}$ was {'added to' if amount >= 0 else 'removed from'} your balance ({current_balance}$ -> {current_balance + amount}$)")
            else:
                raise commands.NotOwner()
        else:
            await ctx.send(f"You have currently {current_balance}$")

async def setup(bot: AceBot):
    await bot.add_cog(Economy(bot))
