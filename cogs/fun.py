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
        self.country_names = None
        self.accuracy = 0
        self.old = None
        self.country = None
        self.playing = False
        self.region: str = 'global'
        self.gamemaster = ctx.author
        self.ctx = ctx
        self.timeout = 120
        self.round = 0
        self.scores: dict[str, int] = {}


    @classmethod
    def random_country(cls):
        countries: list = requests.get('https://restcountries.com/v3.1/all?fields=name,flags,cca3').json()
        yield countries.pop(random.randint(0, len(countries)-1))
    

    @classmethod
    def info(cls, code):
        c: dict = requests.get(f'https://restcountries.com/v3.1/alpha/{code}?fullText=true&fields=capital,region,subregion,languages,demonyms,population').json()
        c_info = []

        capital = c.get('country', None)
        c_info.append(f"{misc.space}capital : `{capital[0]}`") if capital else None

        region = c.get('region', None)
        subregion = c.get('subregion', None)
        c_info.append(f"{misc.space}region : `{subregion}` ({region})") if subregion and region else None

        people = c.get('demonyms', None)
        c_info.append(f"{misc.space}people : `{people['eng']['m']}`") if people else None

        population = c.get('population', None)
        c_info.append(f"{misc.space}population : `{population:,}` habitants") if population else None
        
        return c_info
    

    @classmethod
    def clean_string(cls, string: str) -> bytes:
        return unicodedata.normalize('NFD', string.lower().replace(',', '')).encode('ASCII', 'ignore')
    

    async def config(self):
        embed = discord.Embed(title='\N{EARTH GLOBE AMERICAS} Country Guesser')
        embed.add_field(name='Settings', value=f'\n{misc.space}region : `{self.region}`', inline=False)
        
        start = discord.ui.Button(style=discord.ButtonStyle.green, label='Start')
        start.callback = self.game

        cancel = discord.ui.Button(style=discord.ButtonStyle.red, label='Cancel')
        cancel.callback = self.cancel_game

        view = subclasses.View()
        view.add_item(start)
        view.add_item(cancel)
        self.old = await self.ctx.reply(embed=embed, view=view, mention_author=False)
    

    async def end_game(self, origin: discord.TextChannel):
        games.pop(str(origin.id), None)

        if self.playing:
            self.playing = False
            scores = sorted(self.scores.items(), reverse=True, key=lambda i : i[1])
            scoreboard = map(lambda u : [self.ctx.bot.get_user(int(u[0])).display_name, u[1]], scores)
            embed = discord.Embed(title='End of game', description=f"{misc.space}duration : `{self.START.humanize().replace(' ago', '')}`\n{misc.space}rounds : `{self.round}`\n{misc.space}region : `{self.region}`")
            if len(scores) > 0:
                embed.add_field(name='Scoreboard', value=f"```\n{tabulate([x for x in iter(scoreboard)], headers=['name', 'answers'], numalign='right')}```")

            await origin.send(embed=embed)
    

    async def cancel_game(self, interaction: discord.Interaction):
        if interaction.user == self.gamemaster:
            await interaction.response.edit_message(view=None)
            games.pop(str(interaction.channel_id), None)
        else:
            await interaction.response.send_message('You are not the gamemaster !', ephemeral=True)
    
    
    async def react(self, msg: discord.Message, emoji: discord.PartialEmoji):
        await msg.add_reaction(emoji)


    def check_msg(self, msg: discord.Message):
        if 'quit' in msg.content.casefold() or 'stop' in msg.content.casefold():
            if msg.author == self.gamemaster:
                asyncio.create_task(self.react(msg, '\N{OCTAGONAL SIGN}'))
                asyncio.create_task(self.end_game(msg.channel))
                return
            
        elif 'skip' in msg.content.casefold():
            if msg.author == self.gamemaster:
                asyncio.create_task(self.react(msg, '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}'))
                return True
        
        for n in self.country_names:
            self.accuracy = difflib.SequenceMatcher(None, self.clean_string(msg.content), self.clean_string(n)).ratio()
            if self.accuracy >= 0.65:
                asyncio.create_task(self.react(msg, '\N{WHITE HEAVY CHECK MARK}'))
                return True
            elif self.accuracy >= 0.45:
                asyncio.create_task(self.react(msg, '\N{EYES}'))
                
        return
    

    async def game(self, interaction: discord.Interaction):
        self.playing = True
        # Check if the gamemaster started the game
        if interaction.user == self.gamemaster:
            while self.playing: # Game loop
                if self.round > 20: # 20 games have passed, print results
                    await self.end_game(self.ctx.channel)
                    break
                self.round += 1
                # Set answer
                self.country: dict = next(self.random_country())
                self.country_names: list[str] = [n for n in self.country['name'].values() if type(n) != dict]

                # Game ui
                embed = discord.Embed(title='\N{EARTH GLOBE AMERICAS} What country is this ?')
                embed.add_field(name='Game', value=f'{misc.space}timeout : `{self.timeout//60}min`\n{misc.space}round : `{self.round} of 20`')
                embed.add_field(name='Timer', value=f'{misc.space}{misc.curve}<t:{int(time.time() + self.timeout)}:R>', inline=False)
                embed.set_thumbnail(url=self.country['flags']['png'])

                # Remove components from previous response & send new round
                await self.response.edit(view=None) if hasattr(self, 'response') else None
                self.old = await self.old.edit(view=None, embed=embed) if self.old.embeds[0].title == '\N{EARTH GLOBE AMERICAS} Country Guesser' else await self.old.channel.send(embed=embed)

                self.response_time = time.time()

                try:
                    msg: discord.Message = await self.ctx.bot.wait_for('message', check=self.check_msg, timeout=self.timeout)
                except asyncio.TimeoutError:
                    await self.old.edit(embed=discord.Embed(title='\N{CLOCK FACE ONE OCLOCK} Game terminated', description=f"{misc.space}Players failed to respond within `{self.timeout//60}m`\n{misc.space}{misc.curve} country was `{self.country_names[0]}`", color=discord.Color.red()))
                    await self.end_game(self.old.channel)
                    break
                
                # End (win)
                embed = discord.Embed(title=f'\N{PARTY POPPER} {self.country["name"]["common"]} \N{PARTY POPPER}', description=f'{misc.space}{misc.curve}next in `10s`', color=msg.author.top_role.color if msg.author.top_role.color.value != 0 else None)
                embed.set_author(name=msg.author.display_name, icon_url=msg.author.avatar.url)
                embed.add_field(name='Stats', value=f'{misc.space}accuracy : `{self.accuracy*100:.2f}%`\n{misc.space}time : `{time.time() - self.response_time:.2f}s`\n{misc.space}round : `{self.round} of 20`', inline=False)
                
                info = self.info(self.country['cca3'])
                if len(info) > 0:
                    embed.add_field(name=f"{misc.space}\nInfo", value="\n".join(info), inline=False)

                embed.set_thumbnail(url=self.country['flags']['png'])

                # Save score
                if self.scores.get(str(msg.author.id)):
                    self.scores[str(msg.author.id)] += 1
                else:
                    self.scores[str(msg.author.id)] = 1

                self.response = await self.old.edit(embed=embed)

                # Start next game in 10s
                await asyncio.sleep(10.0)
            

class Fun(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{JIGSAW PUZZLE PIECE}'
        self.bot = bot
    

    @commands.group(invoke_without_command=True)
    async def country(self, ctx: commands.Context):
        if games.get(f'{ctx.channel.id}', None):
            await ctx.reply('An instance of that game is already in play !')
        else:
            games[str(ctx.channel.id)] = 'country'
            game = CountryGuessing(ctx)
            await game.config()
    
    
    @country.command(name='fix')
    async def country_fix(self, ctx: commands.Context, channel: Union[discord.TextChannel, discord.Thread]=lambda ctx : ctx.channel):
        if games.pop(f'{channel.id}', None):
            await ctx.reply(f"Found game in {channel.mention}", mention_author=False)
        else:
            await ctx.reply(f"Did not found any game in {channel.mention}", mention_author=False)
        

async def setup(bot):
    await bot.add_cog(Fun(bot))