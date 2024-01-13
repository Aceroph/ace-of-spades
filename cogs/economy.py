from discord.ext import commands
import discord
import sqlite3
from main import AceBot
from typing import Optional

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot: AceBot = bot
        self.emoji = ":coin:"
        self.connection = sqlite3.connect("database.db")
    
    def get_balance(self, id):
        return self.connection.cursor().execute(f"SELECT money FROM users WHERE id = {id}").fetchall()[0][0]

    @commands.hybrid_command()
    async def balance(self, ctx: discord.Interaction, member: Optional[discord.Member] = None, amount: Optional[int] = None):
        """Checks your current balance or another member's. `Amount` is owner-only"""
        id = member.id if member else ctx.message.author.id
        
        current_balance = self.get_balance(id)
        if amount:
            if await self.bot.is_owner(ctx.message.author):
                self.connection.cursor().execute(f"UPDATE users SET money = ? WHERE id = ?;", (current_balance + amount, id))
                self.connection.commit()
                await ctx.send(f"{abs(amount)}$ was {'added to' if amount >= 0 else 'removed from'} your balance ({current_balance}$ -> {current_balance + amount}$)")
            else:
                raise commands.NotOwner()
        else:
            await ctx.send(f"You have currently {current_balance}$")

async def setup(bot):
    await bot.add_cog(Economy(bot))
