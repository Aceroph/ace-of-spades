import json
import logging
import logging.handlers
import time
from typing import TYPE_CHECKING, Any, Optional

import aiohttp
import asqlite
import asyncio
import discord
from discord.ext import commands

from cogs import EXTENSIONS
from ext import info
from utils.dynamic import QuitButton

if TYPE_CHECKING:
    from games import game

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
    return [p.lower(), p.upper(), bot.user.mention]


class AceBot(commands.Bot):
    def __init__(
        self,
        prefix: str,
        intents: discord.Intents,
        log_handler: Optional[logging.Logger],
        owner_id: int,
        **kwargs
    ):
        super().__init__(
            command_prefix=prefix,
            intents=intents,
            log_handler=log_handler,
            owner_id=owner_id,
            intents=intents,
            help_command=None,
            **kwargs,
        )
        with open("config.json", "r") as cfg:
            self.config: dict[str, Any] = json.load(cfg)

        self.pool: asqlite.Pool
        self.session: aiohttp.ClientSession

        self.boot = time.time()
        self.logger = LOGGER
        self.games: dict[str, "game.Game"] = {}

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

        # Module stuff
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                LOGGER.info("%s loaded", extension)

            except Exception as e:
                LOGGER.error("%s failed to load", extension, exc_info=1)

        # Dynamic items
        self.add_dynamic_items(QuitButton)

        # HTTP stuff
        self.session = aiohttp.ClientSession()

        # Bot info
        self.info = info.Info(self)

    async def close(self):
        await self.session.close()
        await self.pool.close()
        await super().close()

    async def on_ready(self):
        LOGGER.info("Connected as %s (ID: %d)", self.user, self.user.id)

    async def log_commands_run(self, ctx: commands.Context):
        assert ctx.command is not None
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


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    async with asqlite.create_pool(
        "database.db"
    ) as pool, aiohttp.ClientSession() as session:
        async with AceBot(
            prefix=prefix,
            intents=intents,
            log_handler=None,
            owner_id=493107597281329185,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True,
            pool=pool,
            session=session,
        ) as bot:
            bot.start(bot.config["token"])
            await bot.wait_until_ready()
            bot.add_listener(bot.log_commands_run, "on_command_completion")


if __name__ == "__main__":
    asyncio.run(main())
