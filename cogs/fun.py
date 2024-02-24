from typing import TYPE_CHECKING, Union
from utils import subclasses, misc
from discord.ext import commands
from tabulate import tabulate
import unicodedata
import requests
import difflib
import asyncio
import discord
import random
import arrow
import time

if TYPE_CHECKING:
    from main import AceBot

games = {}

class CountryGuessing:
    def __init__(self, ctx: commands.Context) -> None:
        self.START = arrow.get(time.time())
        self.region: str = 'global'
        self.gamemaster = ctx.author
        self.ctx = ctx
        self.timeout = 120
        self.round = 1
        self.scores: dict[str, int] = {}

    @classmethod
    def random_country(cls):
        countries = requests.get('https://restcountries.com/v3.1/all?fields=name,flags,cca3').json()
        yield random.choice(countries)
    
    @classmethod
    def clean_string(cls, string: str) -> str:
        return unicodedata.normalize('NFD', string.lower().replace(',', '')).encode('ASCII', 'ignore')
    
    async def config(self, interaction: discord.Interaction=None):
        embed = discord.Embed(title='\N{EARTH GLOBE AMERICAS} Country Guesser')
        embed.add_field(name='Settings', value=f'\n{misc.space}region : `{self.region}`', inline=False)
        
        start = discord.ui.Button(style=discord.ButtonStyle.green, label='Start')
        start.callback = self.game

        cancel = discord.ui.Button(style=discord.ButtonStyle.red, label='Cancel')
        cancel.callback = self.quit_callback

        view = subclasses.View()
        view.add_item(start)
        view.add_item(cancel)
        self.old = await self.ctx.reply(embed=embed, view=view, mention_author=False) if not interaction else await interaction.response.edit_message(embed=embed, view=view)
    
    async def quit_callback(self, interaction: discord.Interaction):
        if interaction.user == self.gamemaster:
            self.playing = False
            games.pop(str(interaction.channel.id)) if games.get(str(interaction.channel.id)) else None
            await interaction.response.edit_message(view=None)
        else:
            await interaction.response.send_message('You are not the gamemaster !', ephemeral=True)
    
    async def game(self, interaction: discord.Interaction):
        self.playing = True
        # Check if the gamemaster started the game
        if interaction.user == self.gamemaster:
            while self.playing: # Game loop
                if self.round > 20: # 20 games have passed, print results
                    break
                # Set answer
                self.country: dict = next(self.random_country())
                self.country_names: list[str] = [n for n in self.country['name'].values() if type(n) != dict]

                # Game ui
                embed = discord.Embed(title='\N{EARTH GLOBE AMERICAS} What country is this ?')
                embed.add_field(name='Game', value=f'{misc.space}timeout : `{self.timeout//60}min`\n{misc.space}round : `{self.round} of 20`')
                embed.add_field(name='Timer', value=f'{misc.space}{misc.curve}<t:{int(time.time())}:R>', inline=False)
                embed.set_thumbnail(url=self.country['flags']['png'])

                # Remove components from previous view & send main embed
                await self.old.edit(view=None, embed=embed)

                self.response_time = time.time()

                try:
                    msg: discord.Message = await self.ctx.bot.wait_for('message', check=lambda msg : any([r >= 0.50 for r in [difflib.SequenceMatcher(None, self.clean_string(msg.content), self.clean_string(n)).ratio() for n in self.country_names]]), timeout=self.timeout)
                except asyncio.TimeoutError as err:
                    self.playing = False
                    return await self.old.edit(embed=discord.Embed(title='\N{CLOCK FACE ONE OCLOCK} Game terminated', description=f'Players failed to respond within `{self.timeout//60}m`', color=discord.Color.red()))

                for r in [difflib.SequenceMatcher(None, self.clean_string(msg.content), self.clean_string(n)).ratio() for n in self.country_names]:
                    if r >= 0.50:
                        accuracy = r*100
                        break
                
                # End (win)
                embed = discord.Embed(title=f'\N{PARTY POPPER} {self.country["name"]["common"]} \N{PARTY POPPER}', description=f'{misc.space}{misc.curve}next in `10s`', color=msg.author.top_role.color if msg.author.top_role.color.value != 0 else None)
                embed.set_author(name=msg.author.display_name, icon_url=msg.author.avatar.url)
                c = requests.get(f'https://restcountries.com/v3.1/alpha/{self.country["cca3"]}?fullText=true&fields=capital,region,subregion,languages,demonyms,population')
                embed.add_field(name='Stats', value=f'{misc.space}accuracy : `{accuracy:.2f}%`\n{misc.space}time : `{time.time() - self.response_time:.2f}s`\n{misc.space}round : `{self.round} of 20`', inline=False)
                if c.status_code == 200:
                    c = c.json()
                    embed.add_field(name=f'{misc.space}\nInfo', value=f"{misc.space}capital : `{c['capital'][0]}`\n{misc.space}region : `{c['subregion']}` ({c['region']})\n{misc.space}people : `{c['demonyms']['eng']['m']}s`\n{misc.space}population : `{c['population']:,}` habitants", inline=False)
                embed.set_thumbnail(url=self.country['flags']['png'])

                # Save score
                if self.scores.get(str(msg.author.id)):
                    self.scores[str(msg.author.id)] += 1
                else:
                    self.scores[str(msg.author.id)] = 1

                _quit = discord.ui.Button(style=discord.ButtonStyle.red, label='Quit')
                _quit.callback = self.quit_callback

                view = subclasses.View()
                view.add_item(_quit)

                self.old = await msg.reply(embed=embed, view=view, mention_author=False)

                # Start next game in 10s
                await asyncio.sleep(10.0)
                self.round += 1
            
            # End of game, show scores
            scoreboard = sorted(self.scores.items(), reverse=True, key=lambda i : i[1])
            scoreboard = map(lambda u : [self.ctx.bot.get_user(int(u[0])).display_name, u[1]], scoreboard)
            embed = discord.Embed(title='End of game', description=f'{misc.space}duration : `{self.START.humanize().replace(' ago', '')}`\n{misc.space}rounds : `{self.round}`\n{misc.space}region : `{self.region}`')
            embed.add_field(name='Scoreboard', value=f"```\n{tabulate([x for x in iter(scoreboard)], headers=['name', 'answers'], numalign='right')}```")

            await self.old.edit(embed=embed)
                
            

class Fun(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{JIGSAW PUZZLE PIECE}'
        self.bot = bot
        self.games = {}
    

    @commands.command()
    async def country(self, ctx: commands.Context):
        if games.get(f'{ctx.channel.id}', None):
            await ctx.reply('An instance of that game is already in play !')
        else:
            games[str(ctx.channel.id)] = 'country'
            game = CountryGuessing(ctx)
            await game.config()
        

async def setup(bot):
    await bot.add_cog(Fun(bot))