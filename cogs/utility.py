from typing import Union
from discord.ext import commands
import discord
import utils
from main import AceBot

class Utility(utils.Cog):
    def __init__(self, bot: AceBot):
        super().__init__()
        self.bot: AceBot = bot
        self.emoji = utils.EMOJIS["tools"]


    @commands.Cog.listener("on_voice_state_update")
    async def party_event(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        party_config = self.bot.connection.cursor().execute(self.bot.queries["GET_VALUE"], {"key": "party_id", "id": member.guild.id}).fetchall()[0][0]
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
        # in case i forgot to make one
        self.bot.connection.cursor().execute(self.bot.queries["CREATE_CONFIG"])
        self.bot.connection.commit()
        """Sets the party lobby"""
        if channel:
            id = channel if type(channel) is int else channel.id or ctx.channel.id
            self.bot.connection.cursor().execute(self.bot.queries["SET_VALUE"], {"id": ctx.guild.id, "key": "party_id", "value": id}).fetchone()
            self.bot.connection.commit()
            if isinstance(channel, discord.VoiceChannel):
                await ctx.send(f"Party lobby is now {channel.mention}")
            else:
                await ctx.send("Disabled party lobby")
        else:
            channel_id = self.bot.connection.cursor().execute(self.bot.queries["GET_VALUE"], {"id": ctx.guild.id, "key": "party_id"}).fetchone()
            channel = self.bot.get_channel(channel_id[0])
            await ctx.send(f"Current channel is {channel.mention if isinstance(channel, discord.VoiceChannel) else None}")

async def setup(bot: AceBot):
    await bot.add_cog(Utility(bot))
