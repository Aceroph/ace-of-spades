from typing import Dict, Any, Iterable, TYPE_CHECKING
from utils import misc, subclasses
from discord.ext import commands
from tabulate import tabulate
import discord
import random
import string
import arrow
import time

if TYPE_CHECKING:
    from main import AceBot


class SubconfigSelect(discord.ui.Select):
    def __init__(self, setting: str, parent: "ConfigSelect", game: "Game"):
        self.parent = parent
        self.game = game

        super().__init__(
            options=[
                discord.SelectOption(label=option) for option in game.config[setting]
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
        sub_config_view = discord.ui.View()
        setting = self.values[0]
        sub_config_view.add_item(SubconfigSelect(setting, parent=self, game=self.game))
        embed = discord.Embed(
            title=f"\N{GEAR}\N{VARIATION SELECTOR-16} Select {setting}",
            description=f"> Current: `{getattr(self.game, setting)}`",
            color=discord.Colour.green(),
        )
        await interaction.response.send_message(
            embed=embed, view=sub_config_view, ephemeral=True
        )


class ConfigView(subclasses.View):
    def __init__(self, bot: "AceBot", game: "Game", timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.game = game
        self.bot = bot
        self.add_item(ConfigSelect(game=game))

    @discord.ui.button(label="Save", disabled=True, row=2)
    async def save(self, interaction: discord.Interaction, button: discord.Button):
        pass

    @discord.ui.button(label="Play", style=discord.ButtonStyle.green, row=2)
    async def play(self, interaction: discord.Interaction, button: discord.Button):
        await self.game.start(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        self.bot.games.pop(interaction.channel_id, None)
        if interaction.guild:
            await self.quit(interaction, interaction.user)
        else:
            await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="Profile", disabled=True, row=2)
    async def profile(self, interaction: discord.Interaction, button: discord.Button):
        pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.game.gamemaster:
            await interaction.response.send_message(
                content="You are not the Gamemaster!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        self.bot.games.pop(self.game.ctx.channel.id, None)


class Game:
    def __init__(self, ctx: commands.Context) -> None:
        self.START = arrow.get(time.time())
        self.title: str = ""
        self.playing = False
        self.ctx = ctx
        self.id = "".join(random.choices(string.ascii_letters + string.digits, k=6))

        # Game config
        self.gamemaster: discord.abc.User = ctx.author
        self.timeout: int = 120
        self.config: Dict[str, Iterable[Any]] = {}

    def update_menu(self):
        embed = discord.Embed(title=self.title)
        embed.add_field(
            name="Settings",
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
        score_headers: Iterable[str] = None,
        scores: Dict[str, int] = {},
    ):
        self.ctx.bot.games.pop(origin.id, None)
        self.playing = False

        # Get all scores and send the final results
        scores = {
            f"{'*' if score == max(scores.values()) else ''}{self.ctx.bot.get_user(user).name}": score
            for user, score in sorted(scores.items(), key=lambda s: s[1], reverse=True)
        }

        embed = discord.Embed(
            title="End of game",
            description=f"{misc.space}duration : `{self.START.humanize(only_distance=True)}`\n",
        )
        if len(scores) > 0:
            embed.add_field(
                name=f"{misc.space}\nScoreboard",
                value=f"```\n{tabulate(scores.items(), headers=score_headers)}```",
            )
        await origin.send(embed=embed)

    async def track_stats(self, user: discord.User, accuracy: int) -> None:
        async with self.ctx.bot.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO statistics (id, key, value) VALUES (?, ?, 1) ON CONFLICT(id, key) DO UPDATE SET value = value + 1;",
                (
                    user.id,
                    "COUNTRY:rounds",
                ),
            )
            await conn.execute(
                "INSERT INTO statistics (id, key, value) VALUES (:id, :key, :value) ON CONFLICT(id, key) DO UPDATE SET value = value + :value;",
                {"id": user.id, "key": "COUNTRY:accuracy", "value": accuracy},
            )

        await conn.commit()

    def text_input(self, msg: discord.Message):
        pass

    async def start(self, interaction: discord.Interaction):
        pass
