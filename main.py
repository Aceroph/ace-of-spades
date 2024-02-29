from utils import subclasses, misc
from discord.ext import commands
from cogs import EXTENSIONS
from typing import Union
import logging.handlers
import traceback
import textwrap
import discord
import asqlite
import difflib
import pathlib
import logging
import dotenv
import time
import copy

# FILE MANAGEMENT
directory = pathlib.Path(__file__).parent

LOGGER = logging.getLogger('discord')
LOGGER.setLevel(logging.INFO)
logging.getLogger('discord.http').setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
    filename='discord.log',
    encoding='utf-8',
    maxBytes=32 * 1024 ** 2,
    backupCount=5
)
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
handler.setFormatter(formatter)
LOGGER.addHandler(handler)


class AceHelp(commands.HelpCommand):
    old: discord.Embed = None
    old_view: subclasses.View = None

    async def show_info(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.old, view=self.old_view)

    async def show_commands(self, interaction: discord.Interaction):
        if self.context.author == interaction.user:
            self.old = interaction.message.embeds[0]
            embed = discord.Embed(color=discord.Color.blurple())
            embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Documents_icon_-_noun_project_5020_-_white.svg/1200px-Documents_icon_-_noun_project_5020_-_white.svg.png")
            embed.set_author(name=f"{self.context.author.display_name}: Help", icon_url=self.context.author.avatar.url)

            # Modules & Commands
            for name, module in self.context.bot.cogs.items():
                # Filter commands
                filtered_commands = await self.filter_commands(module.get_commands())
                cmds = [f'`{command.qualified_name}`' for command in filtered_commands]
                embed.add_field(name=f"{module.emoji} {name} - {len(cmds)}", value=' '.join(cmds), inline=False) if len(cmds) > 0 else None

            view = subclasses.View()
            info = discord.ui.Button(label='Back to help', emoji='\N{INFORMATION SOURCE}')
            info.callback = self.show_info
            view.add_item(info)
            view.add_quit(interaction.user)
            return await interaction.response.edit_message(embed=embed, view=view)
        else:
            return await interaction.response.send_message("This is not your instance !", ephemeral=True)
    
    async def send_bot_help(self, mapping):
        embed = discord.Embed(color=discord.Color.blurple(), title='Help Page', description='⤷ Use `b.help command/group` for more info on a command')
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Documents_icon_-_noun_project_5020_-_white.svg/1200px-Documents_icon_-_noun_project_5020_-_white.svg.png")
        embed.set_author(name=f"{self.context.author.display_name} : Help", icon_url=self.context.author.avatar.url)

        # Syntax
        embed.add_field(name='Command Syntax', value="⤷ Regarding command usage, it's best to refer to it's dedicated page", inline=False)
        embed.add_field(name='Arguments', value='⤷ `<argument>`: This argument is required\n⤷ `[argument]` : This argument is optional', inline=False)
        
        # Side note
        embed.set_footer(text='Do not type in the brackets or any ponctuation !')

        # View
        view = subclasses.View()
        info = discord.ui.Button(label="Show commands", style=discord.ButtonStyle.grey, emoji='\N{INFORMATION SOURCE}')
        info.callback = self.show_commands
        view.add_item(info)
        self.old_view = view.add_quit(self.context.author)
        
        await self.context.reply(embed=embed, view=view)
    
    async def send_command_help(self, command: Union[commands.Command, commands.Group]):
        if command not in await self.filter_commands(self.context.bot.walk_commands()):
            raise commands.CheckFailure
        
        embed = discord.Embed(color=discord.Color.blurple(), title=f"{misc.tilde} {self.context.prefix}{command.qualified_name} {command.signature}")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Documents_icon_-_noun_project_5020_-_white.svg/1200px-Documents_icon_-_noun_project_5020_-_white.svg.png")
        embed.set_author(name=f"{self.context.author.display_name} : Help -> {command.cog.qualified_name}", icon_url=self.context.author.avatar.url)

        # Documentation
        embed.add_field(name="Documentation", value=f">>> {command.help.format(curve=misc.curve) if command.help else 'Couldn\'t fetch documentation\nI probably forgot to write one for this command :skull:'}", inline=False)

        # Subcommands if group
        if isinstance(command, commands.Group):
            embed.add_field(name=f"Sub commands", value=f"{misc.curve}" + f"\n{misc.space}".join(textwrap.wrap(text=" ".join([f"`{command.name}`" for command in command.commands]), width=50)), inline=True)
        
        # Aliases if any
        if command.aliases != []:
            embed.add_field(name=f"Aliases", value=f"{misc.curve} `{'` `'.join(command.aliases)}`", inline=True)
        
        return await self.context.reply(embed=embed, view=subclasses.View().add_quit(self.context.author))
    
    async def send_group_help(self, group: commands.Group):
        return await self.send_command_help(group)

    async def send_error_message(self, error):
        await self.context.reply(error)


class AceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=dotenv.dotenv_values('.env')["PREFIX"], intents=discord.Intents.all(), help_command=AceHelp(), log_handler=None)
        self.token = dotenv.dotenv_values('.env')["TOKEN"]
        self.owner_id = 493107597281329185
        self.boot = time.time()
        self.LOGGER = LOGGER

    async def setup_hook(self):
        # Database stuff
        self.pool = await asqlite.create_pool('database.db')
        LOGGER.info('Created connection to database')

        async with self.pool.acquire() as conn:
            tables = [name[0] for name in await conn.fetchall("select name from sqlite_master where type='table';")]
            if not 'economy' in tables:
                LOGGER.info('economy table missing from database, creating one...')
                await conn.execute("CREATE TABLE economy ( id INTEGER NOT NULL, money INTEGER DEFAULT (0));")
            
            if not 'guildConfig' in tables:
                LOGGER.info('guildConfig table missing from database, creating one...')
                await conn.execute("CREATE TABLE guildConfig ( id INTEGER NOT NULL, key TEXT NOT NULL, value INTEGER DEFAULT (0), PRIMARY KEY(id, key) );")

            await conn.commit()

        # Module stuff
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                LOGGER.info("%s loaded", extension)

            except Exception as e:
                LOGGER.error("%s failed to load", extension, exc_info=1)
    
    async def close(self):
        await self.pool.close()
        await super().close()

    async def on_ready(self):
        LOGGER.info('Connected as %s (ID: %d)', self.user, self.user.id)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            # Search for possible command (Discusting code down here)
            def find_command(query: list):
                for string in query[::-1]:
                    x = difflib.get_close_matches(string, [cmd.qualified_name for cmd in self.walk_commands()])
                    if len(x) > 0:
                        return self.get_command(x[0])
                return
            
            query = ctx.message.content.strip(self.command_prefix).split()
            command = find_command(query=query)

            if command:
                async def yes_callback(interaction: discord.Interaction):
                    alt_msg = copy.copy(ctx.message)
                    alt_msg._update({'content': f'{self.command_prefix}{command} {" ".join(query[2:]) if len(query) > 2 else ""}'})
                    alt_ctx = await self.get_context(alt_msg, cls=type(ctx))

                    await interaction.message.delete()
                    await interaction.response.defer()
                    return await alt_ctx.command.invoke(alt_ctx)
                
                async def no_callback(interaction: discord.Interaction):
                    await interaction.message.delete()
                    return await interaction.response.defer()
                
                view = subclasses.View()
                # Buttons
                yes = discord.ui.Button(label='Yes', style=discord.ButtonStyle.green)
                no = discord.ui.Button(label='No', style=discord.ButtonStyle.red)

                yes.callback = yes_callback
                no.callback = no_callback
                
                view.add_item(yes)
                view.add_item(no)
                return await ctx.reply(f'Did you mean `{self.command_prefix}{command}` ?', view=view)
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.message.add_reaction('\N{DOUBLE EXCLAMATION MARK}')
            return await ctx.reply(embed=discord.Embed(title=':warning: Missing permissions', description=f"> `{'` `'.join(error.missing_permissions)}`", color=discord.Color.red()))
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.add_reaction('\N{DOUBLE EXCLAMATION MARK}')
            return await ctx.reply(embed=discord.Embed(title=':warning: Missing Required Argument', description=f"> {' '.join(error.args)}", color=discord.Color.red()))
        
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.message.add_reaction('\N{DOUBLE EXCLAMATION MARK}')
            return await ctx.reply(embed=discord.Embed(title=':warning: No Private Message', description=f'> This command cannot be used in DMs', color=discord.Color.red()))

        if isinstance(error, (commands.CheckFailure, commands.NotOwner)):
            return

    async def error_handler(self, ctx: Union[discord.Interaction, commands.Context], error: Exception):
        author = ctx.user or ctx.author

        # Process the traceback to clean path !
        trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        embed = discord.Embed(title=f":warning: Unhandled error in command : {ctx.command if hasattr(ctx, 'command') else 'None'}", description=f"```py\n{misc.clean_traceback(trace)}```")
        embed.set_footer(text=f'Caused by {author.display_name} in {ctx.guild.name if ctx.guild else 'DMs'} ({ctx.guild.id if ctx.guild else 0})', icon_url=author.avatar.url)

        view = subclasses.View()
        view.add_quit(author)

        # Owner embed w full traceback
        await self.get_user(self.owner_id).send(embed=embed)
        await ctx.message.add_reaction('\N{DOUBLE EXCLAMATION MARK}')

        # User error
        embed = discord.Embed(title=f':warning: {type(error).__qualname__}', description=f'> {" ".join(error.args)}' if len(error.args) > 0 else None)
        await ctx.reply(embed=embed, view=view, mention_author=False) or await ctx.response.send_message(embed=embed, view=view)


if __name__ == "__main__":
    bot = AceBot()
    bot.run(bot.token)
