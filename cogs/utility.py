from discord.ext import commands
import discord
from main import AceBot

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot: AceBot = bot
        self.emoji = ":tools:"
        self.vcs = []

    @commands.Cog.listener("on_voice_state_update")
    async def party_event(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        party_config = self.bot.get_guild_config(member.guild.id, "party_id")[0][0]
        if party_config:
            name = member.name + "'s vc"
            if after.channel and after.channel.id == party_config:
                vc = await member.guild.create_voice_channel(name=name, category=after.channel.category)
                self.vcs.append(vc)
                await member.move_to(vc)
            
            if before.channel and before.channel in self.vcs and after.channel != before.channel:
                if not len(before.channel.members):
                    await before.channel.delete()
    
    @commands.hybrid_command()
    async def party(self, ctx: commands.Context):
        """An all-in-one menu to configure your own voice channel"""
        await ctx.send("*Insert a complete dashboard of your party here* (im lazy)")
    
    @commands.hybrid_command(name="party-config", aliases=["vc-config"])
    @commands.is_owner()
    async def party_config(self, ctx: commands.Context, channel: discord.VoiceChannel = None):
        """Sets the party lobby"""
        self.bot.set_guild_config(ctx.guild.id, "party_id", channel.id if channel else 0)
        if channel:
            await ctx.send(f"Party lobby is now {channel.mention}")
        else:
            await ctx.send("Disabled party lobby")

async def setup(bot):
    await bot.add_cog(Utility(bot))
