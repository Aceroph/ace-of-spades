from discord.ext.commands._types import CoroFunc
from discord.utils import MISSING
from utils import subclasses, misc
from discord.ext import commands
from cogs import EXTENSIONS
from typing import Union
import logging.handlers
import textwrap
import discord
import asqlite
import aiohttp
import pathlib
import logging
import dotenv
import time

# FILE MANAGEMENT
directory = pathlib.Path(__file__).parent

LOGGER = logging.getLogger("discord")
LOGGER.setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
    filename="discord.log", encoding="utf-8", maxBytes=32 * 1024**2, backupCount=5
)
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
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
            embed.set_thumbnail(url=misc.docs)
            embed.set_author(
                name=f"{self.context.author.display_name}: Help",
                icon_url=self.context.author.avatar.url,
            )

            # Modules & Commands
            for name, module in self.context.bot.cogs.items():
                # Filter commands
                filtered_commands = await self.filter_commands(module.get_commands())
                cmds = [f"`{command.qualified_name}`" for command in filtered_commands]
                (
                    embed.add_field(
                        name=f"{module.emoji} {name} - {len(cmds)}",
                        value="\n".join(
                            textwrap.wrap(
                                " | ".join(cmds),
                                width=70,
                                initial_indent=f"{misc.space}",
                                subsequent_indent=f"{misc.space}",
                                break_long_words=False,
                            )
                        ),
                        inline=False,
                    )
                    if len(cmds) > 0
                    else None
                )

            view = subclasses.View()
            info = discord.ui.Button(
                label="Back to help", emoji="\N{INFORMATION SOURCE}"
            )
            info.callback = self.show_info
            view.add_item(info)
            view.add_quit(interaction.user)
            return await interaction.response.edit_message(embed=embed, view=view)
        else:
            return await interaction.response.send_message(
                "This is not your instance !", ephemeral=True
            )

    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            color=discord.Color.blurple(),
            title="Help Page",
            description=f"> Use `b.help command/group` for more info on a command",
        )
        embed.set_thumbnail(url=misc.docs)
        embed.set_author(
            name=f"{self.context.author.display_name} : Help",
            icon_url=self.context.author.avatar.url,
        )

        # Syntax
        embed.add_field(
            name="Command Syntax",
            value=f"> Regarding command usage, it's best to refer to it's dedicated page",
            inline=False,
        )
        embed.add_field(
            name="Arguments",
            value=f">>> `<arg>` -> This argument is required\n`[arg]` -> This argument is optional",
            inline=False,
        )

        # Side note
        embed.set_footer(text="Do not type in the brackets or any ponctuation !")

        # View
        view = subclasses.View()
        info = discord.ui.Button(
            label="Show commands",
            style=discord.ButtonStyle.grey,
            emoji="\N{INFORMATION SOURCE}",
        )
        info.callback = self.show_commands
        view.add_item(info)
        self.old_view = view.add_quit(self.context.author)

        await self.context.reply(embed=embed, view=view)

    async def send_command_help(self, command: Union[commands.Command, commands.Group]):
        if command not in await self.filter_commands(self.context.bot.walk_commands()):
            raise commands.CheckFailure

        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f"{misc.tilde} {self.context.prefix}{command.qualified_name} {command.signature}",
        )
        embed.set_thumbnail(url=misc.docs)
        embed.set_author(
            name=f"{self.context.author.display_name} : Help -> {command.cog.qualified_name}",
            icon_url=self.context.author.avatar.url,
        )

        # Documentation
        failure = "Failed to fetch documentation\nProbably forgot to write one for this command\nThis is awkward.."
        embed.add_field(
            name="Documentation",
            value=f">>> {command.help.format(curve=misc.curve) if command.help else failure}",
            inline=False,
        )

        # Subcommands if group
        if isinstance(command, commands.Group):
            embed.add_field(
                name=f"Sub commands",
                value=f"{misc.curve}"
                + f"\n{misc.space}".join(
                    textwrap.wrap(
                        text=" ".join(
                            [f"`{command.name}`" for command in command.commands]
                        ),
                        width=50,
                    )
                ),
                inline=True,
            )

        # Aliases if any
        if command.aliases != []:
            embed.add_field(
                name=f"Aliases",
                value=f"{misc.curve} `{'` `'.join(command.aliases)}`",
                inline=True,
            )

        return await self.context.reply(
            embed=embed, view=subclasses.View().add_quit(self.context.author)
        )

    async def send_group_help(self, group: commands.Group):
        return await self.send_command_help(group)

    async def send_error_message(self, error):
        await self.context.reply(error)


def prefix(bot: "AceBot", msg: discord.abc.Messageable):
    p = dotenv.dotenv_values(".env")["PREFIX"]
    return [p.lower(), p.upper()]


class AceBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=prefix,
            help_command=AceHelp(),
            log_handler=None,
            *args,
            **kwargs,
        )
        self.token = dotenv.dotenv_values(".env")["TOKEN"]
        self.owner_id = 493107597281329185
        self.case_insensitive = True
        self.boot = time.time()
        self.logger = LOGGER

    async def setup_hook(self):
        # Database stuff
        self.pool = await asqlite.create_pool("database.db")
        LOGGER.info("Created connection to database")

        async with self.pool.acquire() as conn:
            tables = {
                "economy": "CREATE TABLE economy ( id INTEGER NOT NULL, money INTEGER DEFAULT (0));",
                "guildConfig": "CREATE TABLE guildConfig ( id INTEGER DEFAULT (0), key TEXT NOT NULL, value BLOB, PRIMARY KEY(id, key));",
                "statistics": "CREATE TABLE statistics (id INTEGER DEFAULT (0), key TEXT NOT NULL, value INTEGER DEFAULT (0), PRIMARY KEY(id, key));",
            }
            existing_tables = [
                name[0]
                for name in await conn.fetchall(
                    "SELECT name FROM sqlite_master WHERE type = 'table';"
                )
            ]
            for table, schema in tables.items():
                if table not in existing_tables:
                    LOGGER.info(
                        "%s table missing from database, creating one..." % table
                    )
                    await conn.execute(schema)

            await conn.commit()

        # HTTP stuff
        self.session = aiohttp.ClientSession()

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
        LOGGER.info("Connected as %s (ID: %d)", self.user, self.user.id)

    async def log_commands_run(self, ctx: commands.Context):
        async with self.pool.acquire() as conn:
            # +1 command ran
            await conn.execute(
                "INSERT INTO statistics (id, key, value) VALUES (?, ?, 1) ON CONFLICT(id, key) DO UPDATE SET value = value + 1;",
                (
                    ctx.guild.id if ctx.guild else 0,
                    "CMD_RAN:" + ctx.command.qualified_name,
                ),
            )
            await conn.commit()


if __name__ == "__main__":
    # Intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = AceBot(intents=intents)
    bot.add_listener(bot.log_commands_run, "on_command_completion")
    bot.run(bot.token)
