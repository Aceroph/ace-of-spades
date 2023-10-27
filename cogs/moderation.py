from discord.ext import commands

from main import AceBot


class Moderation(commands.Cog):
    def __init__(self, bot: AceBot):
        self.bot = bot

    @commands.hybrid_command()
    async def test(self, ctx: commands.Context):
        await ctx.send("balls")


async def setup(bot):
    await bot.add_cog(Moderation(bot))
