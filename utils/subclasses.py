from discord.ext import commands
import discord
import time
import traceback


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
        embed = discord.Embed(title=":warning: Unhandled error in interaction", description=f"```\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```")
        await interaction.client.get_user(493107597281329185).send(embed=embed)
        return await interaction.response.send_message(":warning: Unhandled error in interaction")