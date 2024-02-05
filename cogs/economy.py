from discord.ext import commands
import discord
import sqlite3
from main import AceBot
from typing import Optional
from utility.sql_querries import *

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot: AceBot = bot
        self.emoji = ":coin:"

    @commands.command()
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[int] = None):
        """Checks your current balance or another member's"""
        id = member.id if member else ctx.message.author.id
        
        current_balance = get_balance(self.bot.connection, id)
        if amount:
            if await self.bot.is_owner(ctx.message.author):
                set_balance(self.bot.connection, id, amount)
                await ctx.send(f"{abs(amount)}$ was {'added to' if amount >= 0 else 'removed from'} your balance ({current_balance}$ -> {current_balance + amount}$)")
            else:
                raise commands.NotOwner()
        else:
            await ctx.send(f"You have currently {current_balance}$")

async def setup(bot: AceBot):
    await bot.add_cog(Economy(bot))
