from discord.ext import commands
import requests

class Image(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = 'http://aceroph.pythonanywhere.com/image?key=i39TEyIxtUoh7eeaiS5326Al9DUgylBc&'
    
    @commands.hybrid_group()
    async def image(self, ctx: commands.Context):
        await ctx.send("wip")
    
    @image.command()
    async def query(self, ctx: commands.Context, filename: str):
        r = requests.get(self.url + f'action=query&filename={filename}')
        text = r.text

        await ctx.send(text)
    
    @image.command()
    async def upload(self, ctx: commands.Context, url: str, filename: str):
        request = self.url + f'action=upload&filename={filename}&url={url}'
        print(request)
        r = requests.get(request)
        text = r.text
        
        await ctx.send(text)


async def setup(bot):
    await bot.add_cog(Image(bot))