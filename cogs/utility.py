from typing import Union
from discord.ext import commands
import discord
from utils import EMOJIS, subclasses, ui
from main import AceBot, LOGGER


class Utility(subclasses.Cog):
    def __init__(self, bot: AceBot):
        super().__init__()
        self.bot: AceBot = bot
        self.emoji = EMOJIS["tools"]
        self.vcs = {}
    
    def cog_load(self):
        self.bot.add_view(ui.PartyMenu(self.bot, self.vcs))
        LOGGER.info("Loaded persistent view %s from %s", ui.PartyMenu.__qualname__, self.qualified_name)

    @commands.Cog.listener("on_voice_state_update")
    async def party_event(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        party_config = self.bot.connection.cursor().execute(self.bot.queries["GET_VALUE"], {"key": "party_id", "id": member.guild.id}).fetchall()[0][0]
        if party_config:
            name = member.name + "'s vc"
            if after.channel and after.channel.id == party_config:
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
            # if the channel isnt registered to vcs or the owner left the vc, change the owner to author
            if str(vc.id) not in self.vcs.keys() or self.bot.get_user(self.vcs[str(vc.id)]) not in vc.members:
                msg = f"Transfered party ownership to {ctx.author.mention}"
                self.vcs[str(vc.id)] = ctx.author.id

            embed = discord.Embed(color=discord.Color.gold(), title=f"{EMOJIS['loud_sound']} {vc.name}", description=f"Owner : {self.bot.get_user(self.vcs[str(vc.id)]).mention}\nCreated : <t:{int(vc.created_at.timestamp())}:R>")
            menu = ui.PartyMenu(self.bot, self.vcs)
            await ctx.reply(msg, embed=embed, view=menu)
        elif vc:
            await ctx.reply(":warning: You are not in a party !")
        else:
            await ctx.reply(":warning: You are not in a vc !")
    
    @party.command(name="config")
    @commands.is_owner()
    async def party_config(self, ctx: commands.Context, channel: Union[discord.VoiceChannel, int] = None):
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
