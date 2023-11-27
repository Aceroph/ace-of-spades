from discord.ext import commands
import discord
from discord import app_commands

import json
import asyncio
import pytz
from datetime import datetime
from typing import Optional, Literal
import sqlite3

initial_extensions = [
    "cogs.moderation",
    "cogs.utility"
]


def prettyCog(cog: str):
    return cog.split('.')[1].capitalize()


def prefix(bot, msg):
    client_id = bot.user.id
    return ['a.', f'<@!{client_id}> ', f'<@{client_id}> ']

def loadConfig(file):
    with open(file, 'r') as cfg:
        return json.load(cfg)

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
        self.config = loadConfig("config.json")
        self.token = self.config["TOKEN"]
    
    async def getConfig(self, key, interaction: discord.Interaction=None):
        try:
            return self.config[key]
        except Exception as e:
            if interaction:
                await interaction.response.send_message(e)
            else:
                print(e)

    @staticmethod
    def getCogs():
        cogs = {}
        for cog in initial_extensions:
            if cog in asyncio.run(bot.getConfig("DISABLED_COGS")):
                cogs[cog] = "disabled"

            elif bot.get_cog(cog.split('.')[1].capitalize()):
                cogs[cog] = "loaded"

            else:
                cogs[cog] = "failed"
        return cogs

    async def setup_hook(self):
        await self.add_cog(Debug(self))

        for extension in initial_extensions:
            if extension not in await self.getConfig("DISABLED_COGS"):
                try:
                    await self.load_extension(extension)
                    print(f"{extension} loaded !")

                except Exception as e:
                    print(f"{extension} failed to load ! : {e}")
            else:
                print(f"{extension} disabled !")

    async def on_ready(self):
        print(f'Connected as {self.user} (ID: {self.user.id})')

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("https://tenor.com/view/nuh-uh-beocord-no-lol-gif-24435520")
        else:
            await ctx.reply(error)


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
        e.set_footer(text=datetime.strftime(datetime.now(tz=pytz.timezone('US/Eastern')), "Today at %I:%M%P"))

        e.description = ""
        for cog in self.getCogs():
            status = self.getCogs()[cog]

            if status == "loaded":
                status = ":white_check_mark:"

            elif status == "disabled":
                status = ":octagonal_sign:"

            else:
                status = ":arrows_counterclockwise:"

            e.description += f"{status} {prettyCog(cog)}\n"

        await ctx.send(embed=e)

    @cogs.command()
    @app_commands.choices(cog=[app_commands.Choice(name=prettyCog(cog), value=cog) for cog in bot.getCogs()])
    async def reload(self, ctx: commands.Context, cog: str):
        try:
            await bot.reload_extension(cog)
            await ctx.reply(f":arrows_counterclockwise: Reloaded cog {cog}")
        except Exception as e:
            await ctx.reply(f":octagonal_sign: Couldn't reload __{cog}__ : `{e}`")

    @commands.hybrid_group()
    @commands.is_owner()
    async def debug(self, ctx: commands.Context):
        await ctx.send("WIP")

    @debug.command()
    async def sql(self, ctx: commands.Context, command: str):
        try:
            r = bot.db.cursor().execute(command).fetchall()
            bot.db.commit()

            await ctx.send("Done !" if r is None else r)

        except Exception as e:
            await ctx.send(e)


if __name__ == "__main__":
    bot.run(bot.token)
