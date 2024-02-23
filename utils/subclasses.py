from discord.ext import commands
import traceback
import discord
import time


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def add_quit(self, author: discord.User, row: int=None):
        self.author = author
        button = discord.ui.Button(style=discord.ButtonStyle.red, label='Quit', row=row)
        button.callback = self.quit_callback
        return self.add_item(button)

    async def quit_callback(self, interaction: discord.Interaction):
        if interaction.user == self.author:
            await interaction.message.delete()
        else:
            await interaction.response.send_message('This is not your instance !', ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        embed = discord.Embed(title=":warning: Unhandled error in interaction", description=f"```\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```")
        await interaction.client.get_user(493107597281329185).send(embed=embed)
        return await interaction.followup.send(":warning: Unhandled error in interaction")

    async def on_timeout(self):
        self.clear_items()