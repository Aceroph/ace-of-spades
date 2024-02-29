import copy
from discord.ext import commands
from . import misc
from typing import TYPE_CHECKING
import discord
import time

if TYPE_CHECKING:
    from main import AceBot


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
        bot: 'AceBot' = interaction.client
        await bot.error_handler(interaction, error)

    async def on_timeout(self):
        self.clear_items()


class Paginator:
    def __init__(self, ctx: commands.Context, embed: discord.Embed, max_lines: int=25) -> None:
        self.embed = embed
        self.index: int = 0
        self.max_lines = max_lines
        self.ctx = ctx
        self.view = View()

        self.pages = []
        self.current_page = []

        # Buttons
        _previous = discord.ui.Button(emoji="\N{BLACK LEFT-POINTING TRIANGLE}", disabled=True)
        _previous.callback = self.previous_page
        self.view.add_item(_previous)

        self.view.add_quit(ctx.author)

        _next = discord.ui.Button(emoji="\N{BLACK RIGHT-POINTING TRIANGLE}")
        _next.callback = self.next_page
        self.view.add_item(_next)
    

    def add_line(self, line: str = '') -> None:
        self.current_page.append(line)

        if len(self.current_page) == self.max_lines-1:
            self.pages.append('\n'.join(self.current_page))
            self.current_page = []
    

    def check_buttons(self, interaction: discord.Interaction):
        self.view.clear_items()

        _previous = discord.ui.Button(emoji="\N{BLACK LEFT-POINTING TRIANGLE}", disabled=self.index == 0)
        _previous.callback = self.previous_page
        self.view.add_item(_previous)

        self.view.add_quit(interaction.user)

        _next = discord.ui.Button(emoji="\N{BLACK RIGHT-POINTING TRIANGLE}", disabled=self.index == len(self.pages)-1)
        _next.callback = self.next_page
        self.view.add_item(_next)


    async def start(self):
        self.pages.append('\n'.join(self.current_page))

        self.embed.description = self.pages[self.index]
        self.embed.set_footer(text=f'Page {self.index+1} of {len(self.pages)}')
        await self.ctx.reply(embed=self.embed, view=self.view, mention_author=False)


    async def next_page(self, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            self.index += 1

            self.check_buttons(interaction)

            page = self.pages[self.index]
            embed = interaction.message.embeds[0]
            embed.description = page
            embed.set_footer(text=f'Page {self.index+1} of {len(self.pages)}')
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await interaction.response.send_message("This is not your instance !", ephemeral=True)


    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            self.index -= 1
            
            self.check_buttons(interaction)

            page = self.pages[self.index]
            embed = interaction.message.embeds[0]
            embed.description = page
            embed.set_footer(text=f'Page {self.index+1} of {len(self.pages)}')
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await interaction.response.send_message("This is not your instance !", ephemeral=True)
    
    