from typing import Optional, TYPE_CHECKING
from discord.ext import commands
from utils import subclasses
import discord

if TYPE_CHECKING:
    from main import AceBot

class Bank:
    @classmethod
    async def set_wallet(cls, bot: 'AceBot', account: int, amount: int) -> None:
        async with bot.pool.acquire() as conn:
            await conn.execute("UPDATE users SET money = :amount WHERE id = :account;", {'amount': amount, 'account': account})
    
    @classmethod
    async def get_wallet(cls, bot: 'AceBot', account: int) -> int:
        async with bot.pool.acquire() as conn:
            account = await conn.fetchone("SELECT * FROM economy WHERE id = :account;", {'account': account})
            if not account:
                await conn.execute("INSERT INTO economy (id, money) VALUES (:account, :default);", {'id': account, 'default': 20})
                return 20
            return account[1]


class Economy(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{COIN}'
        self.bot = bot

    @commands.command()
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[int] = None):
        """Checks your current balance or another member's"""
        member_id = member.id if member else ctx.message.author.id

        # Get account, if doesn't exist, create one
        balance = await Bank.get_wallet(self.bot, member_id)

        if amount:
            if await self.bot.is_owner(ctx.message.author):
                await Bank.set_wallet(self.bot, member_id, balance + amount)
                await ctx.reply(f"{abs(amount):,}$ was {'added to' if amount >= 0 else 'removed from'} your balance ({balance:,}$ -> {balance + amount:,}$)")
            else:
                raise commands.NotOwner()
        else:
            await ctx.reply(f"You have currently {balance:,}$")

async def setup(bot):
    await bot.add_cog(Economy(bot))
