from discord.ext.commands.context import Context
from typing import List
from utils import misc
from .game import Game
import difflib
import asyncio
import pathlib
import discord
import random
import json
import time

directory = pathlib.Path(__file__).parent


class Country:
    def __init__(self, data: dict) -> None:
        # Country info
        self.names: List[str] = [
            data["name"]["common"],
            data["name"]["official"],
        ]

        self.capital: str = data.get("country", None)
        self.capital: str = self.capital[0] if self.capital else None

        self.region: str = data["region"]
        self.subregion: str = data.get("subregion", None)

        self.people: dict = data.get("demonyms", None)
        self.population: int = data.get("population", None)

        self.flag: str = data["flags"]["png"]


class CountryGuesser(Game):
    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx)
        # Config
        self.config = {
            "region": [
                "global",
                "africa",
                "americas",
                "antarctic",
                "asia",
                "europe",
                "oceania",
            ],
            "rounds": [5, 10, 15, 20],
            "difficulty": ["flags only"],
            "gamemode": ["multiplayer"],
        }
        self.region = "global"
        self.rounds = 20
        self.difficulty = "flags only"
        self.gamemode = "multiplayer"

        # Game stuff
        self.scores = {}

    async def end_game(self, origin: discord.TextChannel):
        return await super().end_game(origin, ["name", "score"], self.scores)

    def text_input(self, msg: discord.Message):
        if msg.content.strip() == "":
            return
        
        if msg.author == self.gamemaster:
            if "quit" in msg.content.casefold() or "stop" in msg.content.casefold():
                self.playing = False
                asyncio.create_task(msg.add_reaction("\N{OCTAGONAL SIGN}"))
                asyncio.create_task(self.end_game(msg.channel))
                return True

            if "skip" in msg.content.casefold():
                self.winner = None
                asyncio.create_task(
                    msg.add_reaction(
                        "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}"
                    )
                )
                return True

        self.accuracy = max(
            [
                difflib.SequenceMatcher(
                    None, misc.clean_string(name), misc.clean_string(msg.content)
                ).ratio()
                for name in self.country.names
            ]
        )
        if self.accuracy >= 0.65:
            asyncio.create_task(self.track_stats(msg.author, self.accuracy))
            self.winner = msg.author
            asyncio.create_task(msg.add_reaction("\N{WHITE HEAVY CHECK MARK}"))
            return True
        return

    async def start(self, interaction: discord.Interaction):
        self.playing = True
        self.round = 0
        # Get guesses
        with open(directory / "countries.json", "r") as file:
            data = json.load(file)
            match self.region:
                case "global":
                    countries = [
                        Country(data) for data in random.choices(data, k=self.rounds)
                    ]
                case spec:
                    countries = [
                        Country(data)
                        for data in random.choices(
                            [country for country in data if country["region"].casefold() == spec],
                            k=self.rounds,
                        )
                    ]
            file.close()

        while self.playing:  # Game loop
            self.country = countries[self.round]
            self.round += 1

            # Game ui
            embed = discord.Embed(
                title="\N{EARTH GLOBE AMERICAS} What country is this ?"
            )
            embed.add_field(
                name="Game",
                value=f"{misc.space}timeout : `{self.timeout//60}min`\n{misc.space}round : `{self.round} of {self.rounds}`",
            )
            embed.add_field(
                name="Timer",
                value=f"{misc.space}{misc.curve}<t:{int(time.time() + self.timeout)}:R>",
                inline=False,
            )
            embed.set_thumbnail(url=self.country.flag)
            embed.set_footer(text=f"Game ID : #{self.id}")

            if self.round == 1:
                await interaction.response.defer()
                self.game_msg = await interaction.message.edit(view=None, embed=embed)
            else:
                self.game_msg = await self.ctx.channel.send(embed=embed)

            self.response_time = time.time()

            try:
                msg: discord.Message = await self.ctx.bot.wait_for(
                    "message", check=self.text_input, timeout=self.timeout
                )

            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="\N{CLOCK FACE ONE OCLOCK} Game terminated",
                    description=f"{misc.space}players failed to respond within `{self.timeout//60}m`\n{misc.space}{misc.curve} country was `{self.country.names[0]}`",
                    color=discord.Color.red(),
                )
                embed.add_field(
                    name=f"{misc.space}\nInfo",
                    value="Put info here :)",
                    inline=False,
                )

                embed.set_thumbnail(url=self.country.flag)
                await self.game_msg.edit(embed=embed)
                return await self.end_game(self.ctx.channel)

            # End (win)
            embed = discord.Embed(
                title=f"\N{PARTY POPPER} {self.country.names[0]} \N{PARTY POPPER}",
                description=f"{misc.space}{misc.curve}next in `10s`",
                color=(
                    discord.Color.green()
                    if not hasattr(msg.author, "top_role")
                    or msg.author.top_role.color.value == 0
                    else msg.author.top_role.color
                ),
            )
            if self.winner:
                # Add score
                self.scores[self.winner.id] = self.scores.get(self.winner.id, 0) + int(
                    self.accuracy * 100
                )

                embed.add_field(
                    name="Stats",
                    value=f"{misc.space}accuracy : `{self.accuracy*100:.2f}%`\n{misc.space}time : `{time.time() - self.response_time:.2f}s`\n{misc.space}round : `{self.round} of {self.rounds}`",
                    inline=False,
                )
            else:
                embed.title = f"\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR} {self.country.names[0]}"
                embed.add_field(
                    name="Stats",
                    value=f"{misc.space}round : `{self.round} of {self.rounds}`",
                    inline=False,
                )

            embed.set_author(
                name=msg.author.display_name, icon_url=msg.author.avatar.url
            )

            embed.add_field(
                name=f"{misc.space}\nInfo", value="Info here again :)", inline=False
            )

            embed.set_thumbnail(url=self.country.flag)
            embed.set_footer(text=f"Game ID : #{self.id}")

            await self.game_msg.edit(embed=embed)

            if self.round == self.rounds:
                return await self.end_game(self.ctx.channel)

            # Start next game in 10s
            if self.playing:
                async with interaction.channel.typing():
                    await asyncio.sleep(10.0)
