from discord.ext import commands
import discord

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.vcs = []

    @commands.Cog.listener("on_voice_state_update")
    async def private_vc(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        private_vc_id = await self.bot.getGuildConfig(self.bot.cursor, member.guild.id, "private_vc")
        if private_vc_id:
            name = '🔊' + member.name + "'s vc"
            if after.channel and after.channel.id == private_vc_id:
                vc = await member.guild.create_voice_channel(name=name, category=after.channel.category)
                self.vcs.append(vc)
                await member.move_to(vc)
            
            if before.channel and before.channel in self.vcs and after.channel != before.channel:
                if not len(before.channel.members):
                    await before.channel.delete()

async def setup(bot):
    await bot.add_cog(Utility(bot))
