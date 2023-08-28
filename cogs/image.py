from discord.ext import commands

from main import AceBot


class Image(commands.Cog):
    def __init__(self, bot: AceBot):
        self.bot = bot

    @commands.hybrid_group(fallback="get")
    async def image(self, ctx: commands.Context, name: str):
        if name:
            try:
                url = self.bot.db.cursor().execute(f"SELECT * FROM images WHERE name='{name.lower()}';").fetchall()[0][1]
                await ctx.send(url)
            except Exception as e:
                await ctx.send()



    @image.command()
    async def create(self, ctx: commands.Context, name: str, url: str):
        self.bot.db.cursor().execute("INSERT INTO images VALUES (?, ?)", (name.lower(), url))
        self.bot.db.commit()

        await ctx.send("Done !")


async def setup(bot):
    await bot.add_cog(Image(bot))
