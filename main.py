from utils import subclasses, ui, misc
from typing import Union, Callable
from discord.ext import commands
from cogs import EXTENSIONS
import logging.handlers
import traceback
import discord
import sqlite3
import difflib
import pathlib
import logging
import dotenv
import time
import json
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
    async def send_bot_help(self, mapping):
        embed = discord.Embed(color=discord.Color.blurple(), title='Help Page', description='⤷ Use `b.help command/group` for more info on a command')
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Documents_icon_-_noun_project_5020_-_white.svg/1200px-Documents_icon_-_noun_project_5020_-_white.svg.png")
        embed.set_author(name=f"{self.context.author.display_name} : Help", icon_url=self.context.author.avatar.url)

        # Syntax
        embed.add_field(name='Command Syntax', value="⤷ Regarding command usage, it's best to refer to it's dedicated page", inline=False)
        embed.add_field(name='Arguments', value='⤷ `<argument>`: This argument is required\n⤷ `[argument]` : This argument is optional', inline=False)
        
        # Side note
        embed.set_footer(text='Do not type in the brackets or any ponctuation !')
        
        await self.context.reply(embed=embed, view=ui.HelpView(self.context.bot, self.context))
    
    async def send_command_help(self, command: Union[commands.Command, commands.Group]):
        if command not in await self.filter_commands(self.context.bot.commands):
            raise commands.CheckFailure
        
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Documents_icon_-_noun_project_5020_-_white.svg/1200px-Documents_icon_-_noun_project_5020_-_white.svg.png")
        embed.set_author(name=f"{self.context.author.display_name} : Help -> {command.qualified_name.capitalize()}", icon_url=self.context.author.avatar.url)

        # Description & name
        embed.add_field(
            name=f"{command.cog.emoji} {command.qualified_name.capitalize()} {'(Owner-only)' if any(func.__qualname__ == commands.is_owner().predicate.__qualname__ for func in command.checks) else ''}",
            value='⤷ ' + command.short_doc if command.short_doc else "⤷ No description *yet*",
            inline=False
        )

        # Aliases if any
        if command.aliases != []:
            embed.add_field(name="Aliases", value=f"`{'` `'.join(command.aliases)}`")
        
        # Show usage
        clean_signature = f'{self.context.prefix}{command.name} {" ".join([f"<{name}>" if param.required else f"[{name}]" for name, param in command.params.items()])}'
        embed.add_field(name="Usage", value=f"```\n{clean_signature}```\nWhere `< Required >` & `[ Optional ]`", inline=False)

        # Subcommands if group
        if isinstance(command, commands.Group):
            embed.add_field(name="Sub commands", value=" ".join([f"`{command.name}`" for command in command.commands]), inline=False)
        
        return await self.context.reply(embed=embed)
    
    async def send_group_help(self, group: commands.Group):
        return await self.send_command_help(group)

    async def send_error_message(self, error):
        await self.context.reply(error)


class AceBot(commands.Bot):
    def __init__(self):
        self.help = AceHelp()
        super().__init__(command_prefix=dotenv.dotenv_values('.env')["PREFIX"], intents=discord.Intents.all(), help_command=self.help, log_handler=None)
        self.connection = sqlite3.connect(directory / 'database.db')
        self.token = dotenv.dotenv_values('.env')["TOKEN"]
        self.queries = json.load(open(directory / 'sql.json'))
        self.owner_id = 493107597281329185
        self.boot_time = time.time()

    async def setup_hook(self):
        # Create tables in case they do not exist
        self.connection.cursor().execute("CREATE TABLE IF NOT EXISTS users ( id INTEGER NOT NULL, money INTEGER DEFAULT (0), xp INTEGER DEFAULT (0) );")
        self.connection.cursor().execute("CREATE TABLE IF NOT EXISTS guildConfig ( id INTEGER NOT NULL, key TEXT NOT NULL, value INTEGER DEFAULT (0), PRIMARY KEY(id, key) );")
        self.connection.commit()

        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                LOGGER.info("%s loaded", extension)

            except Exception as e:
                LOGGER.error("%s failed to load", extension, exc_info=1)

    async def on_ready(self):
        LOGGER.info('Connected as %s (ID: %d)', self.user, self.user.id)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            # Search for possible command (Discusting code down here)
            filter_cmd: Callable[[str]] = lambda q : difflib.get_close_matches(q, [cmd.qualified_name for cmd in self.commands])
            filter_sub: Callable[[str, commands.Group]] = lambda sub, cmd : difflib.get_close_matches(f'{cmd.qualified_name} {sub}', [subcmd.qualified_name for subcmd in cmd.commands])[0]
            
            split = ctx.message.content.strip(self.command_prefix).split()
            q = split[0]
            if len(split) > 1 and isinstance(self.get_command(filter_cmd(q)), commands.Group):
                command = filter_sub(self.get_command(filter_cmd(q)[0]), split[1])
            else:
                command = filter_cmd(q)

            if len(command) > 0:
                async def yes_callback(interaction: discord.Interaction):
                    alt_msg = copy.copy(ctx.message)
                    alt_msg._update({'content': f'{self.command_prefix}{command[0]} {" ".join(split[2:]) if len(split) > 2 else ""}'})
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
                return await ctx.reply(f'Did you mean `{self.command_prefix}{command[0]}` ?', view=view)
            else:
                return await ctx.reply(":warning: This command does not exist !")
        
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply(":warning: Yous lacking thy necessary rights to perform thus action !")
        
        if isinstance(error, commands.NotOwner):
            return await ctx.reply(":warning: " + error.args)
        
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply(f":warning: {' '.join(error.args).capitalize()}")

        if isinstance(error, commands.CheckFailure):
            return await ctx.reply(":warning: You are not allowed to run that command !")

        embed = discord.Embed(title=":warning: Unhandled error in command", description=f"```\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```")
        await self.get_user(493107597281329185).send(embed=embed)
        return await ctx.reply(":warning: Unhandled error in command !")


if __name__ == "__main__":
    bot = AceBot()
    bot.run(bot.token)
