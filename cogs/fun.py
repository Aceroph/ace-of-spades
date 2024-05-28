from __future__ import annotations
from utils import subclasses, misc, errors
from typing import TYPE_CHECKING
from discord.ext import commands
from tabulate import tabulate
import unicodedata
import requests
import difflib
import asyncio
import discord
import random
import arrow
import time

if TYPE_CHECKING:
    from main import AceBot
    from discord import Interaction
    from discord.ui import Button


games = {}


class ConfigView(subclasses.View):
    def __init__(self, *, game: CountryGuessing, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.game = game
        self.add_item(ConfigSelect(game=game))

    @discord.ui.button(label="Save", disabled=True, row=2)
    async def save(self, interaction: Interaction, button: Button):
        pass

    @discord.ui.button(label="Play", style=discord.ButtonStyle.green, row=2)
    async def play(self, interaction: Interaction, button: Button):
        await self.game.start(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction: Interaction, button: Button):
        games.pop(interaction.channel_id, None)
        if interaction.guild:
            await self.quit(interaction, interaction.user)
        else:
            await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="Profile", disabled=True, row=2)
    async def profile(self, interaction: Interaction, button: Button):
        pass

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.game.gamemaster:
            await interaction.response.send_message(
                content="You are not the Gamemaster!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        games.pop(self.game.ctx.channel.id, None)


class ConfigSelect(discord.ui.Select):
    view: ConfigView

    def __init__(self, game: CountryGuessing):
        self.game = game
        options = [
            discord.SelectOption(label="Change difficulty", value="difficulty"),
            discord.SelectOption(label="Change region", value="region"),
            discord.SelectOption(label="Change gamemode", value="gamemode"),
        ]
        super().__init__(options=options, placeholder="Configure game")

    async def callback(self, interaction: Interaction):
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


class SubconfigSelect(discord.ui.Select):
    def __init__(self, setting: str, parent: ConfigSelect, game: CountryGuessing):
        self.parent = parent
        self.game = game
        match setting:
            case "region":
                options = [discord.SelectOption(label="Global", default=True)]
                options.extend(
                    [
                        discord.SelectOption(label=region, value=region.lower())
                        for region in (
                            "Africa",
                            "Americas",
                            "Antarctic",
                            "Asia",
                            "Europe",
                            "Oceania",
                        )
                    ]
                )

            case "difficulty":
                options = [discord.SelectOption(label="Flags only", default=True)]

            case "gamemode":
                options = [discord.SelectOption(label="Multiplayer", default=True)]

        super().__init__(
            options=options,
        )

    async def callback(self, interaction: Interaction) -> None:
        setting = self.parent.values[0]
        value = self.values[0]
        setattr(self.game, setting, value)
        await self.game.menu_embed.edit(embed=self.game.update_menu())
        embed = discord.Embed(
            title=f"Edited {setting}",
            description=f"> set to: `{value}`",
        )
        await interaction.response.edit_message(embed=embed, view=None)


class CountryGuessing:
    def __init__(self, ctx: commands.Context) -> None:
        self.START = arrow.get(time.time())
        self.country_names = None
        self.playing = False
        self.country = None
        self.countries = []  # Already used
        self.ctx = ctx

        # Game config
        self.gamemaster = ctx.author
        self.difficulty = "flags only"
        self.region: str = "global"
        self.gamemode = "multiplayer"
        self.timeout = 120
        self.round = 0

        # Player
        self.winner: discord.User = None
        self.scores: dict[str, int] = {}
        self.accuracy = 0

    def random_country(self):
        if self.region == "global":
            countries: list = requests.get(
                f"https://restcountries.com/v3.1/all?fields=name,flags,cca3"
            ).json()
        else:
            countries: list = requests.get(
                f"https://restcountries.com/v3.1/region/{self.region}?fields=name,flags,cca3"
            ).json()
        yield random.choice(countries)

    @classmethod
    def info(cls, code):
        c: dict = requests.get(
            f"https://restcountries.com/v3.1/alpha/{code}?fullText=true&fields=capital,region,subregion,languages,demonyms,population"
        ).json()
        c_info = []

        capital = c.get("country", None)
        c_info.append(f"{misc.space}capital : `{capital[0]}`") if capital else None

        region = c.get("region", None)
        subregion = c.get("subregion", None)
        (
            c_info.append(f"{misc.space}region : `{subregion}` ({region})")
            if subregion and region
            else None
        )

        people = c.get("demonyms", None)
        (
            c_info.append(f"{misc.space}people : `{people['eng']['m']}`")
            if people
            else None
        )

        population = c.get("population", None)
        (
            c_info.append(f"{misc.space}population : `{population:,}` habitants")
            if population
            else None
        )

        return c_info

    @classmethod
    def clean_string(cls, string: str) -> bytes:
        return unicodedata.normalize("NFD", string.lower().replace(",", "")).encode(
            "ASCII", "ignore"
        )

    def update_menu(self):
        embed = discord.Embed(title="\N{EARTH GLOBE AMERICAS} Country Guesser")
        embed.add_field(
            name="Settings",
            value=f"{misc.space}difficulty : `{self.difficulty}`\
                \n{misc.space}gamemode : `{self.gamemode}`\
                \n{misc.space}region : `{self.region}`",
            inline=False,
        )
        return embed

    async def menu(self):
        view = ConfigView(game=self)
        embed = self.update_menu()
        self.menu_embed = await self.ctx.reply(
            embed=embed, view=view, mention_author=False
        )

    async def end_game(self, origin: discord.TextChannel):
        games.pop(origin.id, None)

        self.playing = False

        # Get all scores and send the final results
        scores = sorted(
            self.scores.items(), reverse=True, key=lambda i: i[1]["answers"]
        )
        scoreboard = map(
            lambda u: [
                self.ctx.bot.get_user(int(u[0])).display_name,
                u[1]["answers"],
                format(sum(u[1]["avgAccuracy"]) / u[1]["answers"] * 100, ".2f") + "%",
            ],
            scores,
        )
        embed = discord.Embed(
            title="End of game",
            description=f"{misc.space}duration : `{self.START.humanize(only_distance=True)}`\n{misc.space}rounds : `{self.round}`\n{misc.space}region : `{self.region}`",
        )
        if len(scores) > 0:
            embed.add_field(
                name=f"{misc.space}\nScoreboard",
                value=f"```\n{tabulate([x for x in iter(scoreboard)], headers=['name', 'answers', 'acc %'], colalign=('left', 'center', 'decimal'), tablefmt='rounded_outline')}```",
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

    def check_msg(self, msg: discord.Message):
        if msg.author == self.gamemaster:
            if "quit" in msg.content.casefold() or "stop" in msg.content.casefold():
                self.playing = False
                self.winner = None
                asyncio.create_task(msg.add_reaction("\N{OCTAGONAL SIGN}"))
                asyncio.create_task(self.end_game(msg.channel))
                return True

            elif "skip" in msg.content.casefold():
                self.winner = None
                asyncio.create_task(
                    msg.add_reaction(
                        "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}"
                    )
                )
                return True

        for n in self.country_names:
            self.accuracy = difflib.SequenceMatcher(
                None, self.clean_string(msg.content), self.clean_string(n)
            ).ratio()
            if self.accuracy >= 0.65:
                asyncio.create_task(self.track_stats(msg.author, self.accuracy))
                self.winner = msg.author
                asyncio.create_task(msg.add_reaction("\N{WHITE HEAVY CHECK MARK}"))
                return True
        return

    async def start(self, interaction: discord.Interaction):
        self.playing = True

        while self.playing:  # Game loop
            self.round += 1

            # Set answer
            self.country: dict = next(self.random_country())
            while self.country["cca3"] in self.countries:
                self.country: dict = next(self.random_country())
            self.countries.append(self.country["cca3"])

            self.country_names: list[str] = [
                n for n in self.country["name"].values() if type(n) != dict
            ]

            # Game ui
            embed = discord.Embed(
                title="\N{EARTH GLOBE AMERICAS} What country is this ?"
            )
            embed.add_field(
                name="Game",
                value=f"{misc.space}timeout : `{self.timeout//60}min`\n{misc.space}round : `{self.round} of 20`",
            )
            embed.add_field(
                name="Timer",
                value=f"{misc.space}{misc.curve}<t:{int(time.time() + self.timeout)}:R>",
                inline=False,
            )
            embed.set_thumbnail(url=self.country["flags"]["png"])

            if self.round == 1:
                await interaction.response.defer()
                self.game_msg = await interaction.message.edit(view=None, embed=embed)
            else:
                self.game_msg = await self.ctx.channel.send(embed=embed)

            self.response_time = time.time()

            try:
                msg: discord.Message = await self.ctx.bot.wait_for(
                    "message", check=self.check_msg, timeout=self.timeout
                )

            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="\N{CLOCK FACE ONE OCLOCK} Game terminated",
                    description=f"{misc.space}players failed to respond within `{self.timeout//60}m`\n{misc.space}{misc.curve} country was `{self.country_names[0]}`",
                    color=discord.Color.red(),
                )
                info = self.info(self.country["cca3"])
                if len(info) > 0:
                    embed.add_field(
                        name=f"{misc.space}\nInfo", value="\n".join(info), inline=False
                    )

                embed.set_thumbnail(url=self.country["flags"]["png"])
                await self.game_msg.edit(embed=embed)
                return await self.end_game(self.ctx.channel)

            # End (win)
            embed = discord.Embed(
                title=f"\N{PARTY POPPER} {self.country['name']['common']} \N{PARTY POPPER}",
                description=f"{misc.space}{misc.curve}next in `10s`",
                color=(
                    discord.Color.green()
                    if not hasattr(msg.author, "top_role")
                    or msg.author.top_role.color.value == 0
                    else msg.author.top_role.color
                ),
            )
            if self.winner:
                embed.title = f"\N{PARTY POPPER} {self.country['name']['common']} \N{PARTY POPPER}"
                embed.add_field(
                    name="Stats",
                    value=f"{misc.space}accuracy : `{self.accuracy*100:.2f}%`\n{misc.space}time : `{time.time() - self.response_time:.2f}s`\n{misc.space}round : `{self.round} of 20`",
                    inline=False,
                )
            else:
                embed.title = f"\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR} {self.country['name']['common']}"
                embed.add_field(
                    name="Stats",
                    value=f"{misc.space}round : `{self.round} of 20`",
                    inline=False,
                )

            embed.set_author(
                name=msg.author.display_name, icon_url=msg.author.avatar.url
            )

            info = self.info(self.country["cca3"])
            if len(info) > 0:
                embed.add_field(
                    name=f"{misc.space}\nInfo", value="\n".join(info), inline=False
                )

            embed.set_thumbnail(url=self.country["flags"]["png"])

            # Save score
            if self.winner:
                if self.scores.get(str(self.winner.id)):
                    self.scores[str(self.winner.id)]["answers"] += 1
                    self.scores[str(self.winner.id)]["avgAccuracy"].append(
                        self.accuracy
                    )
                else:
                    self.scores[str(self.winner.id)] = {
                        "answers": 1,
                        "avgAccuracy": [self.accuracy],
                    }

            await self.game_msg.edit(embed=embed)

            if self.round == 20:
                return await self.end_game(self.ctx.channel)

            # Start next game in 10s
            if self.playing:
                async with interaction.channel.typing():
                    await asyncio.sleep(10.0)


class Fun(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        super().__init__()
        self.emoji = "\N{JIGSAW PUZZLE PIECE}"
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, fallback="play")
    async def country(self, ctx: commands.Context):
        """Starts a game of country guesser"""
        if games.get(ctx.channel.id, None):
            await ctx.reply("An instance of that game is already in play !")
        else:
            games[ctx.channel.id] = "country"
            game = CountryGuessing(ctx)
            await game.menu()

    @country.command(name="wiki", aliases=["info"])
    async def country_wiki(self, ctx: commands.Context, *, country: str):
        """Wiki for countries"""
        query = "name" if len(country) > 2 else "alpha"

        countries = requests.get(
            f"https://restcountries.com/v3.1/{query}/{country}?fields=area,capital,currencies,demonyms,flags,gini,languages,maps,name,nativeName,population,region,subregion,timezones"
        )

        if countries.status_code != 404:
            if len(countries.json()) > 1 and isinstance(countries.json(), list):
                names = [c["name"]["official"] for c in countries.json()]
                embed = discord.Embed(
                    title=f"{misc.info} Showing results for {country}..",
                    description=">>> " + "\n".join(names[:7]),
                    color=discord.Color.blurple(),
                )
                return await ctx.reply(embed=embed, mention_author=False)

        else:
            return await ctx.reply(
                f"Found nothing matching `{country}`",
                mention_author=False,
            )

        async with ctx.channel.typing():
            country: dict = (
                countries.json()[0]
                if isinstance(countries.json(), list)
                else countries.json()
            )
            native_names = (
                "native names: `"
                + "` | `".join(
                    list(
                        {
                            country["name"]["nativeName"][lang]["official"]
                            for lang in country["name"]["nativeName"].keys()
                        }
                    )
                )
                + "`"
            )
            languages = (
                "languages: `"
                + "` | `".join(
                    list(
                        {
                            country["languages"][lang]
                            for lang in country["languages"].keys()
                        }
                    )
                )
                + "`"
            )
            capital = (
                f"capital: `{country['capital'][0]}`"
                if country.get("capital", None)
                else None
            )

            geo = [
                f"region: `{country['subregion']}` ({country['region']})",
                f"timezones: `{country['timezones'][0]}` to `{country['timezones'][-1]}`",
                f"area: `{int(country['area']):,} km²`",
            ]

            gini = (
                f"gini index: `{list(country['gini'].values())[0]}` ({list(country['gini'])[0]})"
                if country.get("gini", None)
                else None
            )
            currency = f"currency: `{country['currencies'][list(country['currencies'])[0]]['name']}` ({country['currencies'][list(country['currencies'])[0]]['symbol']})"

            embed = discord.Embed(
                title=f"{misc.info} {country['name']['official']}",
                description=f"{misc.curve} [view on map]({country['maps']['googleMaps']}) | [view on stree view]({country['maps']['openStreetMaps']})",
            )
            embed.set_thumbnail(url=country["flags"]["png"])

            embed.add_field(
                name="Endonyms",
                value=misc.space
                + native_names
                + "\n"
                + misc.space
                + languages
                + "\n"
                + misc.space
                + (capital or "capital: `Unknown`"),
                inline=False,
            )
            embed.add_field(
                name="Geography",
                value=misc.space + f"\n{misc.space}".join(geo),
                inline=False,
            )
            embed.add_field(
                name="Economy",
                value=misc.space
                + currency
                + "\n"
                + misc.space
                + (gini or "gini index: `Unknown`"),
                inline=False,
            )
            embed.add_field(
                name="Demonyms",
                value=misc.space
                + f"\n{misc.space}".join(
                    [
                        f"M: {country['demonyms'][lang]['m']} (`{lang.upper()}`)\n{misc.space}W: {country['demonyms'][lang]['f']} (`{lang.upper()}`)\n"
                        for lang in country["demonyms"].keys()
                        if country["demonyms"][lang]["m"]
                        and country["demonyms"][lang]["f"]
                    ]
                ),
                inline=False,
            )
            embed.add_field(
                name="Population",
                value=f"{misc.space}population: `{country['population']:,}` habitants",
                inline=False,
            )

        view = subclasses.View()
        view.add_quit(
            ctx.author, ctx.guild, emoji=misc.delete, style=discord.ButtonStyle.gray
        )

        await ctx.reply(embed=embed, mention_author=False, view=view)


async def setup(bot):
    await bot.add_cog(Fun(bot))
