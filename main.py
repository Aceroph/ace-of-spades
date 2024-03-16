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
        failure = 'Failed to fetch documentation\nProbably forgot to write one for this command\nThis is awkward..'
        embed.add_field(name="Documentation", value=f">>> {command.help.format(curve=misc.curve) if command.help else failure}", inline=False)

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
        self.logger = LOGGER

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
        if isinstance(error, (commands.errors.CheckFailure, commands.errors.NotOwner)):
            return
        
        if isinstance(error, commands.errors.CommandNotFound):
            # Find close matches
            command = ctx.message.content.split()[0].strip(ctx.prefix)

            # Check for commands the author can use
            available_cmds = []
            for cmd in self.walk_commands():
                try:
                    await cmd.can_run(ctx)
                    available_cmds.append(cmd.qualified_name)
                except:
                    pass

            results = [(difflib.SequenceMatcher(None, command, cmd), cmd) for cmd in available_cmds]
            top_results = sorted(results, reverse=True, key=lambda i : i[0].ratio())[:5]
            clean_results = []
            for r in top_results:
                if r[0].ratio() >= 0.40:
                    _match = r[0].find_longest_match(0, len(command), 0, len(r[1]))
                    longest_match = r[1][_match.b:_match.b + _match.size]
                    clean_results.append(r[1].replace(longest_match, f"**__{longest_match}__**"))

            if len(clean_results) >= 1:
                cmds = '\n'.join(clean_results)
                embed = discord.Embed(title="Did you mean?", description=f">>> {cmds}", color=discord.Color.blurple())
                return await ctx.reply(embed=embed, delete_after=15, mention_author=False)
            return

        await ctx.message.add_reaction('\N{DOUBLE EXCLAMATION MARK}')
        
        if isinstance(error, commands.errors.MissingPermissions):
            return await ctx.reply(embed=discord.Embed(title=':warning: Missing permissions', description=f"> `{'` `'.join(error.missing_permissions)}`", color=discord.Color.red()))
        
        if isinstance(error, commands.errors.MissingRequiredArgument):
            return await ctx.reply(embed=discord.Embed(title=':warning: Missing Required Argument', description=f"> {' '.join(error.args)}", color=discord.Color.red()))
        
        if isinstance(error, commands.errors.NoPrivateMessage):
            return await ctx.reply(embed=discord.Embed(title=':warning: No Private Message', description=f'> This command cannot be used in DMs', color=discord.Color.red()))

        # UNHANDLED ERRORS BELLOW
        # Process the traceback to clean path !
        trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        embed = discord.Embed(title=f":warning: Unhandled error in command : {ctx.command if hasattr(ctx, 'command') else 'None'}", description=f"```py\n{misc.clean_traceback(trace)}```")
        embed.set_footer(text=f"Caused by {ctx.author.display_name} in {ctx.guild.name if ctx.guild else 'DMs'} ({ctx.guild.id if ctx.guild else 0})", icon_url=ctx.author.avatar.url)

        view = subclasses.View()
        view.add_quit(ctx.author)

        # Owner embed w full traceback
        await self.get_user(self.owner_id).send(embed=embed)

        # User error
        embed = discord.Embed(title=f":warning: {type(error).__qualname__}", description=f"> {' '.join(error.args)}" if len(error.args) > 0 else None)
        return await ctx.reply(embed=embed, view=view, mention_author=False)



if __name__ == "__main__":
    bot = AceBot()
    bot.run(bot.token)
