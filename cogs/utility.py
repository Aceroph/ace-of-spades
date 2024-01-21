from typing import Union
from discord.ext import commands
import discord
from main import AceBot

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot: AceBot = bot
        self.emoji = ":tools:"


    @commands.Cog.listener("on_voice_state_update")
    async def party_event(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        party_config = self.bot.get_guild_config(member.guild.id, "party_id")[0][0]
        if party_config:
            name = member.name + "'s vc"
            if after.channel and after.channel.id == party_config:
                await member.move_to(await member.guild.create_voice_channel(name=name, category=after.channel.category, bitrate=63000))
            
            if before.channel and before.channel.bitrate == 63000 and after.channel != before.channel:
                if not before.channel.members:
                    await before.channel.delete()
    
    @commands.group(aliases=["vc", "voice"], invoke_without_command=True)
    async def party(self, ctx: commands.Context):
        """An all-in-one menu to configure your own voice channel"""
        await ctx.send("*Insert a complete dashboard of your party here* (im lazy)")
    
    @party.command(name="config")
    @commands.is_owner()
    async def party_config(self, ctx: commands.Context, channel: Union[discord.VoiceChannel, int] = None):
        """Sets the party lobby"""
        if channel:
            self.bot.set_guild_config(ctx.guild.id, "party_id", channel.id or channel)
            if isinstance(channel, discord.VoiceChannel):
                await ctx.send(f"Party lobby is now {channel.mention}")
            else:
                await ctx.send("Disabled party lobby")
        else:
            channel_id = self.bot.get_guild_config(ctx.guild.id, "party_id")[0][0]
            await ctx.send(f"Current channel is {self.bot.get_channel(channel_id).mention}")

async def setup(bot: AceBot):
    await bot.add_cog(Utility(bot))
