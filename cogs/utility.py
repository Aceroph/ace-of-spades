from typing import Union, Callable, TYPE_CHECKING
from utils import subclasses, ui, sql_querries
from discord.ext import commands
from main import LOGGER
import unicodedata
import discord
import pathlib
import time

if TYPE_CHECKING:
    from main import AceBot

class Utility(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{HAMMER AND WRENCH}'
        self.bot = bot
        self.vcs = {}
        self.lines = 0
    
    def cog_load(self):
        self.bot.add_view(ui.PartyMenu(self.bot, self.vcs))
        LOGGER.info("Loaded persistent view %s from %s", ui.PartyMenu.__qualname__, self.qualified_name)

    @commands.Cog.listener("on_voice_state_update")
    async def party_event(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        party_config = await sql_querries.get_value(self.bot, member.guild.id, 'party_id')
        if party_config:
            name = member.name + "'s vc"
            if after.channel and after.channel.id in party_config:
                vc = await member.guild.create_voice_channel(name=name, category=after.channel.category, bitrate=63000)
                self.vcs[str(vc.id)] = member.id
                await member.move_to(vc)
            
            if before.channel and before.channel.bitrate == 63000 and after.channel != before.channel:
                if not before.channel.members:
                    await before.channel.delete()
                elif len(before.channel.members) == 1:
                    self.vcs[str(before.channel.id)] = before.channel.members[0].id
    
    @commands.group(aliases=["vc", "voice"], invoke_without_command=True)
    async def party(self, ctx: commands.Context):
        """An all-in-one menu to configure your own voice channel"""
        vc = ctx.author.voice.channel if ctx.author.voice else None
        msg = ""
        if vc and vc.bitrate == 63000:
            menu = ui.PartyMenu(self.bot, self.vcs)
            await menu.check_ownership(ctx)

            await ctx.reply(msg, embed=ui.PartyMenu.Embed(ctx, self.vcs), view=ui.PartyMenu(self.bot, self.vcs))
        elif vc:
            await ctx.reply(":warning: You are not in a party !")
        else:
            await ctx.reply(":warning: You are not in a vc !")
    
    @party.command(name="config")
    @commands.guild_only()
    @commands.is_owner()
    async def party_config(self, ctx: commands.Context, channel: Union[discord.VoiceChannel, int] = None):
        """Sets the party lobby"""
        if channel:
            channel_id = channel if type(channel) is int else channel.id or ctx.channel.id
            await sql_querries.set_value(self.bot, ctx.guild.id, 'party_id', channel_id)
            if isinstance(channel, discord.VoiceChannel):
                await ctx.send(f"Party lobby is now {channel.mention}")
            else:
                await ctx.send("Disabled party lobby")
        else:
            channel_id = await sql_querries.get_value(self.bot, ctx.guild.id, 'party_id')
            channel = self.bot.get_channel(*channel_id)
            await ctx.send(f"Current channel is {channel.mention if isinstance(channel, discord.VoiceChannel) else None}")
    
    @commands.command(aliases=['char', 'character'])
    async def charinfo(self, ctx: commands.Context, *, characters: str):
        fn: Callable[[str]] = lambda c : "%s : `%s` -> `\\N{%s}`" % (c, c.encode('unicode-escape'), unicodedata.name(c, 'Found nothing'))
        msg = '\n'.join(map(fn, characters))
        await ctx.reply(msg)
        
    @commands.command(aliases=['stats'])
    async def statistics(self, ctx: commands.Context):
        if self.lines == 0 or not int(self.bot.boot_time - time.time()) % 600:
            async with ctx.typing():
                root = pathlib.Path(__file__).parent.parent
                for file in pathlib.Path(__file__).parent.parent.glob('**/*'):
                    if file.name.endswith(('.py', '.json')) and not any(file.is_relative_to(bad) for bad in root.glob('**/.*')):
                        with open(file, 'r') as f:
                            self.lines += len(f.readlines())
            
        await ctx.reply(f'Total lines : {self.lines}')


async def setup(bot):
    await bot.add_cog(Utility(bot))
