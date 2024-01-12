import ast
import json
from discord.ext import commands
import discord
from discord import app_commands
from discord.ext.commands.core import Command, Group

import pytz
import dotenv
from datetime import datetime
from typing import Optional, Literal
import sqlite3
import traceback
import sys
import copy
import asyncio


def prefix(bot, msg):
    client_id = bot.user.id
    return ['a.', f'<@!{client_id}> ', f'<@{client_id}> ']

def insert_returns(body):
        # insert return stmt if the last expression is a expression statement
        if isinstance(body[-1], ast.Expr):
            body[-1] = ast.Return(body[-1].value)
            ast.fix_missing_locations(body[-1])

        # for if statements, we insert returns into the body and the orelse
        if isinstance(body[-1], ast.If):
            insert_returns(body[-1].body)
            insert_returns(body[-1].orelse)

        # for with blocks, again we insert returns into the body
        if isinstance(body[-1], ast.With):
            insert_returns(body[-1].body)

class AceHelp(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name="Thy help center", icon_url=self.context.bot.user.avatar.url)
        embed.set_footer(text="For more, do a.help `command`")
        for cog in (self.context.bot.cogs).values():
            if cog.get_commands().__len__() > 0:
                filtered = await self.filter_commands(cog.get_commands(), sort=True)
                names = [f"`{command.name}`" for command in filtered]
                available_commands = " ".join(names)
                embed.add_field(name=f"{cog.emoji} {cog.qualified_name}", value=available_commands, inline=False)
        await self.get_destination().send(embed=embed)
    
    async def send_command_help(self, command: Command):
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name="Thy help center", icon_url=self.context.bot.user.avatar.url)
        embed.add_field(name=f" {':crown:' if any(func.__qualname__ == commands.is_owner().predicate.__qualname__ for func in command.checks) else ''} {command.cog.emoji} {command.qualified_name.capitalize()}", value=command.short_doc if command.short_doc else "No description *yet*", inline=False)

        if len(command.aliases) > 0:
            embed.add_field(name="Aliases", value=f"`{'` `'.join(x.capitalize() for x in command.aliases)}`")
        
        # usage
        clean_signature = self.get_command_signature(command).split()
        clean_signature[0] = f"a.{command.name}"
        embed.add_field(name="Usage", value=f"```\n{' '.join(clean_signature)}```\nWhere `< Required >`, `[ Optional ]` & `| Either |`", inline=False)

        embed.set_footer(text="For a global view of the commands, refer to a.help")
        await self.get_destination().send(embed=embed)
    
    async def send_group_help(self, group: Group):
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name="Thy help center", icon_url=self.context.bot.user.avatar.url)
        embed.add_field(name=f"{group.cog.emoji} {group.qualified_name.capitalize()}", value=group.short_doc if group.short_doc else "No description *yet*", inline=False)
        embed.add_field(name="Commands", value=" ".join([f"`{command.name}`" for command in group.commands]), inline=False)
        embed.set_footer(text="For more, do a.help `command`")
        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error):
        await self.get_destination().send(error)


class AceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=prefix, intents=discord.Intents.all(), help_command=AceHelp())
        self.connection = sqlite3.connect("database.db")
        self.token = dotenv.dotenv_values(".env")["TOKEN"]
        self.config: dict = json.load(open("config.json"))

    def get_guild_config(self, id: int, key: Optional[str]=None):
        if key is not None:
            return self.connection.cursor().execute("SELECT value FROM guildConfig WHERE id = ? AND key = ?;", (id, key)).fetchall()
        else:
            return self.connection.cursor().execute(f"SELECT * FROM guildConfig WHERE id = {id};").fetchall()
    
    def set_guild_config(self, id: int, key: str, value: int):
        self.connection.cursor().execute("INSERT INTO guildConfig (id, key, value) VALUES (?, ?, ?) ON CONFLICT (id, key) DO UPDATE SET value=EXCLUDED.value", (id, key, value))
        self.connection.commit()
        return

    async def setup_hook(self):
        await self.add_cog(Debug(self))

        for extension in self.config["initial_modules"]:
            if extension != "debug":
                try:
                    await self.load_extension("cogs." + extension)
                    print(f"{datetime.now().__format__('%Y-%m-%d %H:%M:%S')} INFO     {extension.capitalize()} loaded !")

                except Exception as e:
                    print(f"{datetime.now().__format__('%Y-%m-%d %H:%M:%S')} ERROR    {extension.capitalize()} failed to load ! : {e}")

    async def on_ready(self):
        print(f'Connected as {self.user} (ID: {self.user.id})')

    async def on_command_error(self, ctx, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("https://tenor.com/view/nuh-uh-beocord-no-lol-gif-24435520")
        elif isinstance(error, commands.NotOwner):
            await ctx.reply(error)
        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


class Debug(commands.Cog):
    def __init__(self, bot):
        self.bot: AceBot = bot
        self.emoji = ":space_invader:"


    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, option: Optional[Literal["local", "copy", "clear"]] = None):
        async with ctx.channel.typing():
            match option:
                case "local":
                    synced = await self.bot.tree.sync(guild=ctx.guild)
                case "copy":
                    self.bot.tree.copy_global_to(guild=ctx.guild)
                    synced = await self.bot.tree.sync(guild=ctx.guild)
                case "clear":
                    self.bot.tree.clear_commands(guild=ctx.guild)
                    await self.bot.tree.sync(guild=ctx.guild)
                    synced = []
                case _:
                    synced = await self.bot.tree.sync()
            
        await asyncio.sleep(5)

        await ctx.send(f"Synced {len(synced)} commands {'globally' if option is None else 'to the current guild.'}\n`{' '.join(command.name for command in synced)}`")
        return

    @commands.hybrid_group(fallback="list")
    @commands.is_owner()
    async def modules(self, ctx: commands.Context):
        embed = discord.Embed(color=discord.Color.blurple(), title="Extensions")
        embed.set_footer(text=datetime.strftime(datetime.now(tz=pytz.timezone('US/Eastern')), "Today at %H:%M"))

        embed.description = ""

        for name in bot.cogs:
            if self.bot.get_cog(name):
                embed.description += f"\n{bot.get_cog(name).emoji} {name} `[{'Loaded' if name != 'Debug' else 'Core'}]`"
            else:
                embed.description += f"\n{bot.get_cog(name).emoji} {name} `[Unloaded]`"

        await ctx.send(embed=embed)

    @modules.command(name="reload")
    async def module_reload(self, ctx: commands.Context, module: str):
        try:
            await self.bot.reload_extension(module)
            await ctx.reply(f":arrows_counterclockwise: Reloaded module {module}")
        except Exception as e:
            await ctx.reply(f":octagonal_sign: Couldn't reload `{module}` : `{e}`")

    @module_reload.autocomplete("module")
    async def autocomplete_reload(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=module.capitalize(), value=module) for module in self.bot.config["initial_modules"]]

    @commands.command()
    @commands.is_owner()
    async def sql(self, ctx: commands.Context, command: str):
        try:
            r = self.bot.connection.cursor().execute(command).fetchall()
            self.bot.connection.commit()

            await ctx.send("Done !" if r is None else r)

        except Exception as e:
            await ctx.send(e)
    
    @commands.hybrid_command()
    @commands.is_owner()
    async def sudo(self, ctx: commands.Context, member: discord.Member, *, command: str):
        alt_msg: discord.Message = copy.copy(ctx.message)
        alt_msg.author = member
        alt_msg.content = f"a.{command}"
        alt_ctx = await bot.get_context(alt_msg, cls=type(ctx))
        await ctx.reply(f"Command executed successfully as {member.name}", ephemeral=True)
        await self.bot.invoke(alt_ctx)


    @commands.hybrid_command()
    @commands.is_owner()
    async def eval(self, ctx, flags: Optional[Literal["no-output"]] = None, *, code):
        fn_name = "_eval_expr"

        cmd = code.strip("` ")

        # add a layer of indentation
        cmd = "\n".join(f"    {i}" for i in cmd.splitlines())

        # wrap in async def body
        body = f"async def {fn_name}():\n{cmd}"

        parsed = ast.parse(body)
        body = parsed.body[0].body

        insert_returns(body)

        env = {
            'bot': self.bot,
            'discord': discord,
            'commands': commands,
            'ctx': ctx,
            '__import__': __import__
        }
        exec(compile(parsed, filename="<ast>", mode="exec"), env)

        result = (await eval(f"{fn_name}()", env))
        match flags:
            case "no-output":
                pass
            case _:
                await ctx.send(result)
    

if __name__ == "__main__":
    bot = AceBot()
    bot.run(bot.token)
