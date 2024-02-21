from typing import TYPE_CHECKING
from discord.ext import commands
from utils import subclasses
from io import BytesIO
import requests
import difflib
import discord
import random
import time

if TYPE_CHECKING:
    from main import AceBot

class Fun(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{JIGSAW PUZZLE PIECE}'
        self.bot = bot
        self.countries = None
    
    @commands.command()
    async def country(self, ctx: commands.Context):
        PREFIX = 'guess '
        async with ctx.typing():
            if not self.countries:
                print('Loading countries')
                self.countries: dict = requests.get('https://flagcdn.com/en/codes.json').json()

            code: str = None
            while code is None or len(code) > 2:
                code = random.choice([*self.countries.keys()])
            flag = requests.get(f'https://flagcdn.com/128x96/{code}.png', stream=True).raw.read()
            img = discord.File(BytesIO(flag), filename='country.png')

            # Embed
            embed = discord.Embed(title='What country is this ?', description='You have 60 seconds to guess\nGuess by typing `guess <country>`')
            embed.add_field(name='Timer', value=f'⤷ <t:{int(time.time())}:R>')
            embed.set_thumbnail(url='attachment://country.png')

        await ctx.reply(embed=embed, file=img)
        start = time.time()
        msg = await self.bot.wait_for('message', check=lambda msg : msg.author == ctx.author and msg.content.lower().startswith(PREFIX), timeout=60)
        t: int = time.time() - start
        if difflib.SequenceMatcher(None, msg.content.lower().strip(PREFIX), self.countries[code].lower()).ratio() > 0.85:
            await msg.reply(f'Country was {self.countries[code]}, you guessed it in `{t:.2f} seconds`')
        else:
            await msg.reply(f'Wrong answer ! Answer was `{self.countries[code]}`')


async def setup(bot):
    await bot.add_cog(Fun(bot))