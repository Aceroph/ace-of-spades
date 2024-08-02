import random
import string
import time
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Sequence

import discord
from discord.ext import commands
from tabulate import tabulate

from utils import misc, subclasses

if TYPE_CHECKING:
    from main import AceBot


class SubconfigSelect(discord.ui.Select):
    def __init__(self, setting: str, parent: "ConfigSelect"):
        self.parent = parent
        self.game = parent.game

        super().__init__(
            options=[
                discord.SelectOption(label=option)
                for option in self.game.config[setting]
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        setting = self.parent.values[0]
        value = self.values[0]
        setattr(
            self.game,
            setting,
            await commands.run_converters(
                self.game.ctx,
                type(self.game.config[setting][0]),
                value,
                commands.Parameter,
            ),
        )
        await self.game.menu.edit(embed=self.game.update_menu())
        embed = discord.Embed(
            title=f"Edited {setting}",
            description=f"> set to: `{value}`",
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ConfigSelect(discord.ui.Select):
    view: "ConfigView"

    def __init__(self, game: "Game"):
        self.game = game
        super().__init__(
            options=[
                discord.SelectOption(label=f"Change {setting}", value=setting)
                for setting in game.config.keys()
            ],
            placeholder="Configure game",
        )

    async def callback(self, interaction: discord.Interaction):
        subconfig_view = discord.ui.View()
        setting = self.values[0]
        subconfig_view.add_item(SubconfigSelect(setting, parent=self))
        embed = discord.Embed(
            title=f"\N{GEAR}\N{VARIATION SELECTOR-16} Select {setting}",
            description=f"> Current: `{getattr(self.game, setting)}`",
            color=discord.Colour.green(),
        )
        await interaction.response.send_message(
            embed=embed, view=subconfig_view, ephemeral=True
        )


class ConfigView(subclasses.View):
    def __init__(self, bot: "AceBot", game: "Game", timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.game = game
        self.bot = bot
        self.add_item(ConfigSelect(game=game))

    async def is_gamemaster(self, interaction: discord.Interaction) -> bool:
        """Custom implementation of an interaction check. 
        Returns True if the gamemaster is interacting else responds and return False"""
        if interaction.user == self.game.gamemaster:
            return True
        await interaction.response.send_message(
            content="You are not the Gamemaster!", ephemeral=True
        )
        return False

    @discord.ui.button(label="Save", disabled=True, row=2)
    async def save(self, interaction: discord.Interaction, button: discord.Button):
        if not(self.is_gamemaster(interaction)):
            return 
        pass

    @discord.ui.button(label="Play", style=discord.ButtonStyle.green, row=2)
    async def play(self, interaction: discord.Interaction, button: discord.Button):
        if not(self.is_gamemaster(interaction)):
            return

        for _id, game in self.bot.games.items():
            if isinstance(game, type(self.game)):
                return await interaction.response.send_message(
                    f"An instance of that game is already in play ! (ID: #{_id})",
                    ephemeral=True,
                )

        self.bot.games[self.game.id] = self.game
        self.stop()
        await self.game.start(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        if interaction.guild:
            if not(self.is_gamemaster(interaction)):
                return
            await self.game.menu.delete()
        else:
            await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="Profile", row=2)
    async def profile(self, interaction: discord.Interaction, button: discord.Button):
        async with self.bot.pool.acquire() as conn:
            scores = await conn.fetchall(
                "WITH Leaderboard AS (SELECT id, value, ROW_NUMBER() OVER (ORDER BY value DESC) as row_num FROM statistics WHERE key = :key) SELECT id, value, row_num FROM Leaderboard WHERE id = :id UNION SELECT id, value, row_num FROM Leaderboard WHERE row_num <= 3 ORDER BY value DESC;",
                {
                    "key": f"game.{self.game.__class__.__qualname__}:score",
                    "id": interaction.user.id,
                },
            )
            games = await conn.fetchall(
                "WITH Leaderboard AS (SELECT id, value, ROW_NUMBER() OVER (ORDER BY value DESC) as row_num FROM statistics WHERE key = :key) SELECT id, value, row_num FROM Leaderboard WHERE id = :id UNION SELECT id, value, row_num FROM Leaderboard WHERE row_num <= 3 ORDER BY value DESC;",
                {
                    "key": f"game.{self.game.__class__.__qualname__}:games",
                    "id": interaction.user.id,
                },
            )

        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(
            name=f"{interaction.user.display_name}'s profile",
            icon_url=interaction.user.display_avatar.url,
        )

        ranks = [
            "1st",
            "2nd",
            "3rd",
        ]
        if scores:
            data = [
                [f"{ranks[rank-1]}", user, score] for user, score, rank in scores[:3]
            ]
            if len(scores) == 4:  # if user is not within the top 3
                data.extend(
                    [
                        [None, None, None],
                        [f"{scores[3][2]}th", scores[3][0], scores[3][1]],
                    ]
                )

            leaderboard = tabulate(
                data, headers=["Rank", "User", "Score"], tablefmt="outline"
            )
            embed.add_field(
                name=f"Highest score", value=f"```\n{leaderboard}```", inline=False
            )

        if games:
            data = [
                [f"{ranks[rank-1]}", user, gamesplayed]
                for user, gamesplayed, rank in games[:3]
            ]
            if len(games) == 4:  # if user is not within the top 3
                data.extend(
                    [
                        [None, None, None],
                        [f"{games[3][2]}th", games[3][0], games[3][1]],
                    ]
                )

            leaderboard = tabulate(
                data, headers=["Rank", "User", "Score"], tablefmt="outline"
            )
            embed.add_field(
                name=f"Most games played",
                value=f"```\n{leaderboard}```",
            )

        return await interaction.response.send_message(embed=embed, ephemeral=True)


class Game:
    def __init__(
        self,
        ctx: commands.Context,
        title: Optional[str] = "Untitled game",
        thumbnail: Optional[str] = None,
    ) -> None:
        self.START = time.time()
        self.title = title
        self.thumbnail = thumbnail
        self.playing: bool = False
        self.ctx = ctx
        self.id = "".join(random.choices(string.ascii_letters + string.digits, k=6))

        # Game config
        self.gamemaster: discord.abc.User = ctx.author
        self.timeout: int = 120
        self.config: Dict[str, Sequence[Any]] = {}

    def update_menu(self):
        embed = discord.Embed(title=self.title).set_author(
            name=self.gamemaster.display_name,
            icon_url=self.gamemaster.display_avatar.url,
        )
        embed.set_thumbnail(url=self.thumbnail)
        embed.add_field(
            name="\N{GEAR}\N{VARIATION SELECTOR-16} Settings",
            value="\n".join(
                [
                    f"{misc.space}{setting} : `{getattr(self, setting, 'Unknown')}`"
                    for setting in self.config.keys()
                ]
            ),
        )
        return embed

    async def send_menu(self):
        view = ConfigView(bot=self.ctx.bot, game=self)
        self.menu = await self.ctx.reply(
            embed=self.update_menu(), view=view, mention_author=False
        )

    async def end_game(
        self,
        origin: discord.TextChannel,
        score_headers: Iterable[str] | None = None,
        scores: Dict[str, int] | None = None,
        extras: Dict[str, Any] | None = None,
    ):
        self.ctx.bot.games.pop(self.id, None)
        self.playing = False

        embed = discord.Embed(
            title="End of game",
            description=f"{misc.space}duration : `{misc.time_format(time.time()-self.START)}`",
        )
        if extras:
            for extra, value in extras.items():
                embed.description += f"\n{misc.space}{extra}: {value}"

        if scores and score_headers:
            # Track stats
            for user, score in scores.items():
                await self.track_stats(user, score)

            # Get all scores and send the final results
            scores = {
                f"{'*' if score == max(scores.values()) else ''}{self.ctx.bot.get_user(user).name}": score
                for user, score in sorted(
                    scores.items(), key=lambda s: s[1], reverse=True
                )
            }
            embed.add_field(
                name=f"{misc.space}\nScoreboard",
                value=f"```\n{tabulate(scores.items(), headers=score_headers)}```",
            )

        await origin.send(embed=embed)

    async def track_stats(self, user: discord.User, score: int) -> None:
        async with self.ctx.bot.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO statistics (id, key, value) VALUES (?, ?, 1) ON CONFLICT(id, key) DO UPDATE SET value = value + 1;",
                (
                    user,
                    f"game.{self.__class__.__qualname__}:games",
                ),
            )
            await conn.execute(
                "INSERT INTO statistics (id, key, value) VALUES (:id, :key, :value) ON CONFLICT(id, key) DO UPDATE SET value = value + :value;",
                {
                    "id": user,
                    "key": f"game.{self.__class__.__qualname__}:score",
                    "value": score,
                },
            )

            await conn.commit()

    def text_input(self, msg: discord.Message):
        pass

    async def start(self, interaction: discord.Interaction):
        pass
