from discord.ext import commands
from . import misc
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
        # Process the traceback to clean path !
        trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        embed = discord.Embed(title=":warning: Unhandled error in command", description=f"```py\n{misc.clean_traceback(trace)}```")

        async def send_report(i: discord.Interaction):
            if i.user == interaction.user:
                reponse = discord.Embed(title='Error sent', description='> Thank you for reporting')
                await i.response.edit_message(embed=reponse, view=None, delete_after=5)
                embed.set_footer(text=f'Sent by {i.user.global_name} from {i.guild.name} ({i.guild.id})')
                await i.client.get_user(493107597281329185).send(embed=embed)
            else:
                await i.response.send_message('Only the one who caused the error can report it !', ephemeral=True)

        view = self.__class__()
        report = discord.ui.Button(label='Report', emoji='\N{PUBLIC ADDRESS LOUDSPEAKER}')
        report.callback = send_report
        view.add_item(report)
        view.add_quit(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

    async def on_timeout(self):
        self.clear_items()