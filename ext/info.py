import pathlib
import time
from typing import TYPE_CHECKING, List, Optional

import discord
import psutil
from discord.ext import commands

from utils import misc, subclasses, errors

if TYPE_CHECKING:
    from main import AceBot


class Info:
    def __init__(self, bot: "AceBot") -> None:
        self.last_updated: float = time.time()
        self.bot = bot

        # Lines of code
        self.lines = 0
        self.comments = 0

        # Amount of cogs, commands, guilds and users
        self.commands = len(self.bot.commands)
        self.modules = len(self.bot.cogs)
        self.users = len(self.bot.users)
        self.guilds = len(self.bot.guilds)

        # Process stats
        process = psutil.Process()
        self.pid = process.pid
        self.memory = process.memory_full_info().rss / 1024**2
        self.memory100 = process.memory_percent()
        self.cpu100 = process.cpu_percent()

        # Global stats
        self.commands_ran: int = 0
        self.songs_played: int = 0
        self.playtime: int = 0
        self.top_commands: List = []

        # Fetch info
        self._total_lines()

    async def stats(self, embed: discord.Embed, guild: Optional[discord.Guild] = None):
        async with self.bot.pool.acquire() as conn:
            self.commands_ran = (
                await conn.fetchone(
                    "SELECT total(value) FROM statistics WHERE key LIKE 'CMD_RAN:%';"
                )
            )[0]
            self.songs_played = (
                await conn.fetchone(
                    "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYED';"
                )
            )[0]
            self.playtime = (
                await conn.fetchone(
                    "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYTIME';"
                )
            )[0]

            # TOP COMMANDS
            self.top_commands = await conn.fetchall(
                "SELECT key, value FROM statistics WHERE key LIKE 'CMD_RAN:%' AND id = ? ORDER BY value DESC LIMIT 5;",
                (guild.id or 0),
            )

            local_commands_ran = (
                await conn.fetchone(
                    "SELECT total(value) FROM statistics WHERE key LIKE 'CMD_RAN:%' AND id = ?;",
                    (guild.id if guild else 0),
                )
            )[0]
            medals = [
                "\N{FIRST PLACE MEDAL}",
                "\N{SECOND PLACE MEDAL}",
                "\N{THIRD PLACE MEDAL}",
                "\N{SPORTS MEDAL}",
                "\N{SPORTS MEDAL}",
            ]
            top_commands = f"\n{misc.space}".join(
                [
                    f"{medals[i]} {cmd[0].split(':')[1]}: `{cmd[1]}`"
                    for i, cmd in enumerate(self.top_commands)
                ]
            )

            embed.add_field(
                name="Top commands",
                value=(
                    f"{misc.space}{top_commands}\n\n"
                    f"{misc.space}Total ran: `{self.commands_ran:.0f}`\n"
                    f"{misc.space}{misc.curve} from {'guild' if guild else 'DMs'}: `{local_commands_ran:.0f}`"
                ),
            )

            # Guild only
            if guild:
                guild_songs_played = (
                    await conn.fetchone(
                        "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYED' AND id = ?;",
                        (guild.id),
                    )
                )[0]
                guild_playtime = (
                    await conn.fetchone(
                        "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYTIME' AND id = ?;",
                        (guild.id),
                    )
                )[0]

                embed.add_field(
                    name="Music statistics",
                    value=(
                        f"{misc.space}Total songs played: `{self.songs_played:.0f}`\n"
                        f"{misc.space}{misc.curve} from guild: `{guild_songs_played:.0f}`\n\n"
                        f"{misc.space}Total playtime: `{misc.time_format(self.playtime)}`\n"
                        f"{misc.space}{misc.curve} from guild: `{misc.time_format(guild_playtime)}`"
                    ),
                )

            await conn.close()
            return embed

    def _total_lines(self):
        root = pathlib.Path(__file__).parent.parent
        for file in pathlib.Path(__file__).parent.parent.glob("**/*"):
            if file.name.endswith(".py") and not any(
                file.is_relative_to(bad) for bad in root.glob("**/.*")
            ):
                with open(file, "r") as f:
                    for line in f.readlines():
                        if line.lstrip().startswith("#"):
                            self.comments += 1
                        elif line.strip() != "":
                            self.lines += 1
        return


class InfoView(subclasses.View):
    def __init__(self, bot: "AceBot", author: discord.abc.User) -> None:
        super().__init__()
        self.bot = bot
        self.author = author

        # Check if refreshable
        timer = time.time() - self.bot.info.last_updated
        self.refresh.disabled = timer < 300

    async def embed(self, ctx: commands.Context):
        info: Info = self.bot.info

        embed = discord.Embed(color=discord.Color.blurple())

        embed.set_footer(
            text=f"Made by aceroph using discord.py v{discord.__version__}",
            icon_url=misc.python,
        )
        embed.set_author(
            name=f"View source on github • {self.bot.user.display_name}",
            url=misc.git_source(self.bot),
            icon_url=misc.github,
        )

        embed.add_field(
            name="Community",
            value=(
                f"{misc.space}{misc.server}servers: `{info.guilds}`\n"
                f"{misc.space}{misc.members}users: `{info.users:,}`"
            ),
        )

        embed.add_field(
            name="Timestamps",
            value=(
                f"{misc.space}created on: {discord.utils.format_dt(self.bot.user.created_at, 'd')}\n"
                f"{misc.space}joined on: {discord.utils.format_dt(ctx.guild.me.joined_at, 'd') if ctx.guild else '`never.`'}\n"
                f"{misc.space}uptime: `{misc.time_format(time.time()-self.bot.boot)}`"
            ),
        )
        embed.add_field(
            name=f"Code statistics",
            value=(
                f"{misc.space}lines of code: `{info.lines:,}`\n"
                f"{misc.space}comments: `{info.comments:,}`\n"
                f"{misc.space}commands: `{info.commands}`\n"
                f"{misc.space}modules: `{info.modules}`"
            ),
        )
        embed.add_field(
            name="Process",
            value=(
                f"{misc.space}pid: `{info.pid}`\n"
                f"{misc.space}cpu: `{info.cpu100:.1f}%`\n"
                f"{misc.space}mem: `{info.memory:,.1f}MB` (`{info.memory100:.1f}%`)"
            ),
        )

        return await self.bot.info.stats(embed, ctx.guild)

    @discord.ui.button(label="Refresh")
    async def refresh(self, interaction: discord.Interaction, button: discord.Button):
        if not (
            interaction.user == self.author
            or interaction.user.guild_permissions.administrator
        ):
            raise errors.NotYourButton

        self.bot.info = Info(self.bot)
        self.refresh.disabled = True
        embed = await self.embed(interaction.context)

        return await interaction.response.edit_message(embed=embed, view=self)
