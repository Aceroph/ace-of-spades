from discord.ext import commands
import discord
import time, datetime
import re


class Cog(commands.Cog):
    def __init__(self):
        self.emoji: str = "<:sadcowboy:1002608868360208565>"
        self.time: float = time.time()
        self.cmds = 0
    

    @commands.Cog.listener()
    async def on_command_completion(self, command: commands.Command):
        if hasattr(command.cog, 'cmds') and issubclass(type(command.cog), type(self)):
            command.cog.cmds += 1


class View(discord.ui.View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        await interaction.response.send_message(f"Unhandled error : {error}")


class Time(commands.Converter):      
    async def convert(self, ctx: commands.Context, argument: str):
        # Fixed date like 2024-02-16
        if re.fullmatch("\d{4}-\d{2}-\d{2}", argument):
            return datetime.datetime.strptime(argument, "%Y-%m-%d")

        # Relative date like 1d
        if re.fullmatch("-?\d+d", argument):
            days = int(re.match("-?\d+", argument).group())

            if days > 0:
                return datetime.datetime.today() + datetime.timedelta(days=abs(days))
            else:
                return datetime.datetime.today() - datetime.timedelta(days=abs(days))
        
        return
        