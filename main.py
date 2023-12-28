from discord.ext import commands
import discord
from discord import app_commands

import pytz
import dotenv
from datetime import datetime
from typing import Optional, Literal
import sqlite3
import traceback
import sys

initial_extensions = [
    "cogs.moderation",
    "cogs.utility",
    "cogs.economy"
]


def prettyCog(cog: str):
    return cog.split('.')[1].capitalize()


def prefix(bot, msg):
    client_id = bot.user.id
    return ['a.', f'<@!{client_id}> ', f'<@{client_id}> ']

def loadDatabase():
    connection = sqlite3.connect("database.db")
    return connection.cursor()


class AceHelp(commands.HelpCommand):

    async def send_bot_help(self, mapping):
        filtered = await self.filter_commands(self.context.bot.commands, sort=True)
        names = [command.name for command in filtered]
        available_commands = "\n".join(names)
        embed = discord.Embed(description=available_commands)
        await self.context.send(embed=embed)

    async def send_error_message(self, error):
        await self.get_destination().send(error)


class AceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=prefix, intents=discord.Intents.all(), help_command=AceHelp())
        self.cursor = loadDatabase()
        self.token = dotenv.dotenv_values(".env")["TOKEN"]

    def getGuildConfig(self, cursor: sqlite3.Cursor, id: int, key: str):
        output = cursor.execute(f"SELECT value FROM guildConfig WHERE id = {id} AND key = {key}")
        return output.fetchall()

    @staticmethod
    def getCogs(self, cursor: sqlite3.Cursor, guild: int):
        cogs = {}
        for cog in initial_extensions:
            if cog in self.getGuildConfig(cursor, guild, "DISABLED_COGS"):
                cogs[cog] = "disabled"

            elif bot.get_cog(cog.split('.')[1].capitalize()):
                cogs[cog] = "loaded"

            else:
                cogs[cog] = "failed"
        return cogs

    async def setup_hook(self):
        await self.add_cog(Debug(self))

        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"{extension} loaded !")

            except Exception as e:
                print(f"{extension} failed to load ! : {e}")

    async def on_ready(self):
        print(f'Connected as {self.user} (ID: {self.user.id})')

    async def on_command_error(self, ctx, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("https://tenor.com/view/nuh-uh-beocord-no-lol-gif-24435520")
        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


bot = AceBot()


class Debug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object],
                   spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.hybrid_group()
    @commands.is_owner()
    async def cogs(self, ctx: commands.Context):
        e = discord.Embed(
            color=discord.Color.blurple(),
            title="Extensions"
        )
        e.set_footer(text=datetime.strftime(datetime.now(tz=pytz.timezone('US/Eastern')), "Today at %H:%M"))

        e.description = ""
        for cog in self.bot.getCogs(self.bot.cursor, ctx.guild.id):
            status = self.bot.getCogs(self.bot.cursor, ctx.guild.id)[cog]

            if status == "loaded":
                status = ":white_check_mark:"

            elif status == "disabled":
                status = ":octagonal_sign:"

            else:
                status = ":arrows_counterclockwise:"

            e.description += f"{status} {prettyCog(cog)}\n"

        await ctx.send(embed=e)

    @cogs.command()
    async def reload(self, ctx: commands.Context, cog: str):
        try:
            await bot.reload_extension(cog)
            await ctx.reply(f":arrows_counterclockwise: Reloaded cog {cog}")
        except Exception as e:
            await ctx.reply(f":octagonal_sign: Couldn't reload `{cog}` : `{e}`")

    @reload.autocomplete("cog")
    async def autocomplete_reload(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=prettyCog(cog), value=cog) for cog in bot.getCogs(bot.cursor, interaction.guild_id)]

    @commands.hybrid_group()
    @commands.is_owner()
    async def debug(self, ctx: commands.Context):
        await ctx.send("WIP")

    @debug.command()
    async def sql(self, ctx: commands.Context, command: str):
        try:
            r = bot.cursor.execute(command).fetchall()
            bot.cursor.connection.commit()

            await ctx.send("Done !" if r is None else r)

        except Exception as e:
            await ctx.send(e)


if __name__ == "__main__":
    bot.run(bot.token)
