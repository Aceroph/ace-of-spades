from utils import subclasses, ui, misc
from discord.ext import commands
from cogs import EXTENSIONS
from typing import Union
import logging.handlers
import traceback
import discord
import asqlite
import difflib
import pathlib
import logging
import dotenv
import time
import copy
import re

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
        if command not in await self.filter_commands(self.context.bot.walk_commands()):
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
        embed.add_field(name="Usage", value=f"```\n{clean_signature}```", inline=False)

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
        super().__init__(command_prefix=dotenv.dotenv_values('.env')["PREFIX"], intents=discord.Intents.all(), help_command=AceHelp(), log_handler=None)
        self.token = dotenv.dotenv_values('.env')["TOKEN"]
        self.owner_id = 493107597281329185
        self.boot = time.time()

    async def setup_hook(self):
        self.pool = await asqlite.create_pool('database.db')
        LOGGER.info('Created connection to database')

        # Create tables in case they do not exist
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS users ( id INTEGER NOT NULL, money INTEGER DEFAULT (0), xp INTEGER DEFAULT (0) );")
            await conn.execute("CREATE TABLE IF NOT EXISTS guildConfig ( id INTEGER NOT NULL, key TEXT NOT NULL, value INTEGER DEFAULT (0), PRIMARY KEY(id, key) );")
            await conn.commit()

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
            else:
                return await ctx.reply(":warning: This command does not exist !")
        
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply(":warning: Yous lacking thy necessary rights to perform thus action !")
        
        if isinstance(error, commands.NotOwner):
            return await ctx.reply(":warning: " + error.args)
        
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply(f":warning: {' '.join(error.args).capitalize()}")

        if isinstance(error, commands.CheckFailure):
            if isinstance(error, commands.NoPrivateMessage):
                return await ctx.reply(":warning: You can't use that command in DMs !")
            
            return await ctx.reply(":warning: You are not allowed to run that command !")

        # Process the traceback to clean path !
        trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        await ctx.reply(embed=discord.Embed(title=":warning: Unhandled error in command", description=f"```py\n{misc.clean_traceback(trace)}```"))

if __name__ == "__main__":
    bot = AceBot()
    bot.run(bot.token)
