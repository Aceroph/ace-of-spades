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
str.replace

class View(discord.ui.View):
    def __init__(self, quit: bool=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Quit button
        if quit:
            button = discord.ui.Button(style=discord.ButtonStyle.red, label='Quit', row=2)
            button.callback = self.quit
            self.add_item(button)

    async def quit(self, interaction: discord.Interaction):
        await interaction.message.delete()

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        embed = discord.Embed(title=":warning: Unhandled error in interaction", description=f"```\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```")
        await interaction.client.get_user(493107597281329185).send(embed=embed)
        return await interaction.followup.send(":warning: Unhandled error in interaction")

    async def on_timeout(self):
        self.clear_items()