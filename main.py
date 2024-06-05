from discord.ext import commands
from cogs import EXTENSIONS
import logging.handlers
import discord
import asqlite
import aiohttp
import logging
import time
import json

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


def prefix(bot: "AceBot", msg: discord.abc.Messageable):
    p = bot.config["prefix"]
    return [p.lower(), p.upper()]


class AceBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=prefix,
            log_handler=None,
            owner_id=493107597281329185,
            case_insensitive=True,
            strip_after_prefix = True,
            *args,
            **kwargs,
        )
        with open("config.json", "r") as cfg:
            self.config: dict = json.load(cfg)

        self.boot = time.time()
        self.logger = LOGGER
        self.games = {}

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

    bot = AceBot(intents=intents, help_command=None)
    bot.add_listener(bot.log_commands_run, "on_command_completion")
    bot.run(bot.config["token"])
