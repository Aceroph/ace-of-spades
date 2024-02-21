from utils import subclasses, ui, misc
from typing import TYPE_CHECKING
from discord.ext import commands
from main import LOGGER
import tabulate
import discord

if TYPE_CHECKING:
    from main import AceBot

class Debug(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{DESKTOP COMPUTER}'
        self.bot = bot

    def cog_load(self):
        self.bot.add_view(ui.ModuleMenu(self.bot))
        LOGGER.info("Loaded persistent view %s from %s", ui.ModuleMenu.__qualname__, self.qualified_name)

    @commands.group(invoke_without_command=True)
    async def modules(self, ctx: commands.Context):
        """Lists all modules"""
        return await ctx.reply(embed=ui.ModuleMenu.Embed(self.bot), view=ui.ModuleMenu(self.bot))

    @commands.is_owner()
    @commands.group()
    async def sql(self, ctx: commands.Context, *, command: str):
        """Executes SQL commands to the database"""
        async with self.bot.pool.acquire() as conn:
            r = await conn.fetchall(command) or await conn.execute(command)
            await conn.commit()
            
            if isinstance(r, list):
                r = discord.Embed(description=f'```\n{tabulate.tabulate(headers=r[0].keys(), tabular_data=r)}```')
            else:
                r = discord.Embed(description='Executed !')
            
            await ctx.reply(embed=r)
    
    @commands.command(aliases=["killyourself", "shutdown"])
    @commands.is_owner()
    async def kys(self, ctx: commands.Context):
        """Self-explanatory"""
        await ctx.reply("https://tenor.com/view/pc-computer-shutting-down-off-windows-computer-gif-17192330")
        await self.bot.close()
    
    @commands.command(aliases=["src"])
    async def source(self, ctx: commands.Context, *, obj: str=None):
        """Get the source of any command or cog"""
        url = await misc.git_source(self.bot, obj)
        await ctx.reply(url)


async def setup(bot):
    await bot.add_cog(Debug(bot))