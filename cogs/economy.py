from utils import subclasses, sql_querries
from typing import Optional, TYPE_CHECKING
from discord.ext import commands
import discord

if TYPE_CHECKING:
    from main import AceBot

class Economy(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{COIN}'
        self.bot = bot

    @commands.command()
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[int] = None):
        """Checks your current balance or another member's"""
        member_id = member.id if member else ctx.message.author.id
        
        current_balance = await sql_querries.get_balance(self.bot, member_id)
        if amount:
            if await self.bot.is_owner(ctx.message.author):
                await sql_querries.set_balance(self.bot, member_id, current_balance + amount)
                await ctx.reply(f"{abs(amount):,}$ was {'added to' if amount >= 0 else 'removed from'} your balance ({current_balance:,}$ -> {current_balance + amount:,}$)")
            else:
                raise commands.NotOwner()
        else:
            await ctx.reply(f"You have currently {current_balance:,}$")

async def setup(bot):
    await bot.add_cog(Economy(bot))
