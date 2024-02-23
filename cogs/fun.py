from utils import subclasses, misc
from typing import TYPE_CHECKING
from discord.ext import commands
from io import BytesIO
import unicodedata
import requests
import difflib
import asyncio
import discord
import random
import time

if TYPE_CHECKING:
    from main import AceBot

class CountryGuessing:
    def __init__(self, ctx: commands.Context) -> None:
        self.gamemode = 'solo'
        self.region: str = 'global'
        self.prefix: str = None
        self.player = ctx.author
        self.ctx = ctx

    @classmethod
    def random_country(cls):
        countries = requests.get('https://restcountries.com/v3.1/all?fields=name,flags').json()
        yield random.choice(countries)
    
    @classmethod
    def clean_string(cls, string: str) -> str:
        return unicodedata.normalize('NFD', string.lower().replace(',', '')).encode('ASCII', 'ignore')
    
    async def config(self, interaction: discord.Interaction=None):
        self.embed = discord.Embed(title='\N{EARTH GLOBE AMERICAS} Country Guesser')
        self.embed.add_field(name='Settings', value=f'{misc.space}gamemode : `{self.gamemode}`\n{misc.space}region : `{self.region}`\n{misc.space}prefix : `{str(self.prefix).lower()}`\n{misc.space}timer : `60s`', inline=False)
        view = subclasses.View()
        start = discord.ui.Button(style=discord.ButtonStyle.green, label='Start')
        start.callback = self.game
        view.add_item(start)
        view.add_quit(self.player)
        await self.ctx.reply(embed=self.embed, view=view) if not interaction else await interaction.response.edit_message(embed=self.embed, view=view)
    
    async def game(self, interaction: discord.Interaction):
        if interaction.user == self.player:
            country: dict = next(self.random_country())
            names = [n for n in country['name'].values() if type(n) != dict]

            self.embed.title = '\N{EARTH GLOBE AMERICAS} What country is this ?'
            self.embed.add_field(name='Settings', value=f'{misc.space}prefix : {self.prefix}\n{misc.space}timer : `60s`\n{misc.space}{misc.curve} <t:{int(time.time())}:R>', inline=False)
            self.embed.set_thumbnail(url=country['flags']['png'])

            await interaction.response.edit_message(embed=self.embed, view=None)

            self.timer = time.time()
            msg = await interaction.client.wait_for('message', check=lambda msg : msg.author == self.player and msg.content.lower().startswith(self.prefix if self.prefix else ''))

            for n in names:
                r = difflib.SequenceMatcher(None, self.clean_string(msg.content), self.clean_string(n)).ratio()
                if r >= 0.85:
                    self.embed = discord.Embed(title='\N{CROWN} We have a winner !', description=f'{misc.space}{misc.curve}the country was `{n}`')
                    self.embed.add_field(name='Stats', value=f'{misc.space}accuracy : `{r*100:.2f}%`\n{misc.space}time : `{time.time() - self.timer:.2f}s`')
                    retry_same_config = discord.ui.Button(style=discord.ButtonStyle.blurple, label='New Game')
                    retry_same_config.callback = self.game

                    edit_config = discord.ui.Button(label='Edit config')
                    edit_config.callback = self.config

                    view = subclasses.View()
                    view.add_item(retry_same_config)
                    view.add_item(edit_config)
                    view.add_quit(self.player)
                    await msg.reply(embed=self.embed, view=view)
            

class Fun(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{JIGSAW PUZZLE PIECE}'
        self.bot = bot
        self.countries = None
    

    @commands.command()
    async def country(self, ctx: commands.Context):
        game = CountryGuessing(ctx)
        await game.config()
        

async def setup(bot):
    await bot.add_cog(Fun(bot))