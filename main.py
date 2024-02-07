from discord.ext import commands
import discord
from discord.ext.commands.core import Command, Group
from cogs import EXTENSIONS
import pytz
import dotenv
from datetime import datetime
from typing import Union
import sqlite3
import traceback
import json
import pathlib
import utils

# FILE MANAGEMENT
directory = pathlib.Path(__file__).parent


class AceHelp(commands.HelpCommand):
    async def base_help(self, footer: str, obj: Union[Group, Command] = None):
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name="Thy help center", icon_url=self.context.bot.user.avatar.url)
        embed.set_footer(text=footer)

        # global commands
        if obj is None:
            for cog in (self.context.bot.cogs).values():
                if cog.get_commands().__len__() > 0:
                    filtered = await self.filter_commands(cog.get_commands(), sort=True)
                    names = [f"`{command.name}`" for command in filtered]
                    available_commands = " ".join(names)
                    embed.add_field(name=f"{cog.emoji} {cog.qualified_name}", value=available_commands, inline=False)
        
        else:
            # description & name
            embed.add_field(
                name=f"{':crown:' if any(func.__qualname__ == commands.is_owner().predicate.__qualname__ for func in obj.checks) else ''} {obj.cog.emoji} {obj.qualified_name.capitalize()}",
                value=obj.short_doc if obj.short_doc else "No description *yet*",
                inline=False
            )

            # aliases
            if obj.aliases != []:
                embed.add_field(name="Aliases", value=f"`{'` `'.join(obj.aliases)}`")
            
            # usage
            clean_signature = self.get_command_signature(obj).split()
            clean_signature[0] = f"{self.context.prefix}{obj.name}"
            embed.add_field(name="Usage", value=f"```\n{' '.join(clean_signature)}```\nWhere `< Required >`, `[ Optional ]` & `| Either |`", inline=False)

            if isinstance(obj, Group):
                # sub commands
                embed.add_field(name="Commands", value=" ".join([f"`{command.name}`" for command in obj.commands]), inline=False)
            
        await self.context.reply(embed=embed)

    async def send_bot_help(self, mapping):
        await self.base_help(f"To see a command's usage, refer to {self.context.prefix}help <command>")
    
    async def send_command_help(self, command: Command):
        await self.base_help(f"For all available commands, refer to {self.context.prefix}help", command)
    
    async def send_group_help(self, group: Group):
        await self.base_help(f"For all available commands, refer to {self.context.prefix}help", group)

    async def send_error_message(self, error):
        await self.get_destination().send(error)


class AceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=dotenv.dotenv_values('.env')["PREFIX"], intents=discord.Intents.all(), help_command=AceHelp())
        self.connection = sqlite3.connect(directory / 'database.db')
        self.token = dotenv.dotenv_values('.env')["TOKEN"]
        self.queries = json.load(open(directory / 'sql.json'))

    async def setup_hook(self):
        # create tables in case they do not exist
        self.connection.cursor().execute("CREATE TABLE IF NOT EXISTS users ( id INTEGER NOT NULL, money INTEGER DEFAULT (0), xp INTEGER DEFAULT (0) );")
        self.connection.cursor().execute("CREATE TABLE IF NOT EXISTS guildConfig ( id INTEGER NOT NULL, key TEXT NOT NULL, value INTEGER DEFAULT (0), PRIMARY KEY(id, key) );")
        self.connection.commit()

        await self.add_cog(Debug(self))

        for extension in EXTENSIONS:
            if extension != "debug":
                try:
                    await self.load_extension(extension)
                    print(f"{datetime.now().__format__('%Y-%m-%d %H:%M:%S')} INFO     {extension.capitalize()} loaded !")

                except Exception as e:
                    print(f"{datetime.now().__format__('%Y-%m-%d %H:%M:%S')} ERROR    {extension.capitalize()} failed to load ! : {e}")

    async def on_ready(self):
        print(f'Connected as {self.user} (ID: {self.user.id})')

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            await ctx.reply("This command does not exist ! Please use actual commands :pray:")
        
        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply("Yous lacking thy necessary rights to perform thus action !")
        
        elif isinstance(error, commands.NotOwner):
            await ctx.reply("Such action is reserved to the one who coded it")

        else:
            embed = discord.Embed(title=f"Ignoring exception in command {ctx.command}", description=f"```\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```")
            await ctx.reply(embed=embed)


class Debug(utils.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot: AceBot = bot
        self.emoji = "\ud83d\udc7e"

    @commands.group(invoke_without_command=True)
    async def modules(self, ctx: commands.Context):
        """Lists all modules with their current status"""
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_footer(text=datetime.strftime(datetime.now(tz=pytz.timezone('US/Eastern')), "Today at %H:%M"))
        
        embed.add_field(name="Extensions", value="\n".join([f"{self.bot.get_cog(name).emoji} {name}" for name in self.bot.cogs]), inline=True)

        view = utils.ui.ModuleMenu(self.bot)

        await ctx.send(embed=embed, view=view)

    @commands.command()
    @commands.is_owner()
    async def sql(self, ctx: commands.Context, *, command: str):
        """Executes SQL commands to the database"""
        try:
            r = self.bot.connection.cursor().execute(command).fetchall()
            self.bot.connection.commit()

            await ctx.send("Done !" if r is None else r)

        except Exception as e:
            await ctx.send(e)


if __name__ == "__main__":
    bot = AceBot()
    bot.run(bot.token)
