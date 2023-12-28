from discord.ext import commands
import discord
import sqlite3

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.cursor: sqlite3.Cursor = self.bot.cursor
    
    def getBalance(self, id):
        return self.cursor.execute(f"SELECT money FROM users WHERE id = {id}").fetchall()[0][0]

    @commands.hybrid_command()
    async def balance(self, ctx: discord.Interaction):
        await ctx.send(f"You have currently {self.getBalance(ctx.message.author.id)} $")

    @commands.hybrid_command()
    async def addmoney(self, ctx: discord.Interaction, amount: int):
        balance = self.getBalance(ctx.message.author.id)
        self.cursor.execute(f"UPDATE users SET money = {balance + amount} WHERE id = {ctx.message.author.id}")
        self.cursor.connection.commit()
        await ctx.send(f"{amount} $ was added to your balance")

async def setup(bot):
    await bot.add_cog(Economy(bot))
