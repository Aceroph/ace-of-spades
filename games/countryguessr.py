import aiohttp
import asyncio
import difflib
import json
import pathlib
import random
import time
from io import BytesIO
from typing import List

import discord
from discord.ext.commands.context import Context

from utils import misc

from .game import Game

directory = pathlib.Path(__file__).parent


class Country:
    def __init__(self, data: dict) -> None:
        # Country info
        self.names: List[str] = [
            data["name"]["common"],
            data["name"]["official"],
        ]

        self.capital: str = data.get("capital", None)
        self.capital: str = self.capital[0] if self.capital else "Unknown"

        self.region: str = data["region"]
        self.subregion: str = data.get("subregion", None)

        self.people: dict = data.get("demonyms", None)
        self.population: int = data.get("population", None)

        self.flag: str = data["flags"]["png"]


class CountryGuesser(Game):
    def __init__(self, ctx: Context) -> None:
        super().__init__(
            ctx,
            title="CountryGuesser",
            thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/%C3%86toms_-_Earth.svg/1200px-%C3%86toms_-_Earth.svg.png",
        )  # \N{EARTH GLOBE AMERICAS}
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
        self.scores: dict[str, int] = {}
        self.playing = True
        self.round = 0
        self.winner = None

    async def end_game(self, origin: discord.TextChannel):
        await super().end_game(
            origin,
            score_headers=["name", "score"],
            scores=self.scores,
            extras={"rounds": f"`{self.round}/{self.rounds}`"},
        )

    def text_input(self, msg: discord.Message) -> bool:
        if not (msg.content):
            return False

        if msg.author == self.gamemaster:
            if msg.content.casefold().startswith(("quit", "stop")):
                self.playing = False
                asyncio.create_task(msg.add_reaction("\N{OCTAGONAL SIGN}"))
                asyncio.create_task(self.end_game(msg.channel))
                return True

            if msg.content.casefold().startswith(("skip", "idk")):
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
            self.winner = msg.author
            asyncio.create_task(msg.add_reaction("\N{WHITE HEAVY CHECK MARK}"))
            return True
        return False

    async def start(self, interaction: discord.Interaction):
        ## Get country data
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
                            [
                                country
                                for country in data
                                if country["region"].casefold() == spec
                            ],
                            k=self.rounds,
                        )
                    ]

        ## Game loop
        while self.playing:
            self.country = countries[self.round]
            self.round += 1

            # Getting the flag image from the url to send it as a file
            async with aiohttp.ClientSession() as cs:
                async with cs.get(self.country.flag) as res:
                    _bytes = await res.read()

            buff = BytesIO(_bytes)
            file = discord.File(buff, filename="flag.png")

            # Game ui
            embed = discord.Embed(
                title="\N{EARTH GLOBE AMERICAS} What country is this ?"
            )
            embed.add_field(
                name="Game",
                value=f"{misc.space}timeout : `{self.timeout//60}min`\n{misc.space}round : `{self.round} of {self.rounds}`\n{misc.space}ends <t:{int(time.time() + self.timeout)}:R>\n\n-# Game ID : #{self.id}",
            )
            embed.set_thumbnail(url="attachment://flag.png")

            if self.round == 1:
                await interaction.response.defer()
                self.game_msg = await interaction.message.edit(
                    view=None, embed=embed, attachments=[file]
                )  # send the file as well
            else:
                self.game_msg = await self.ctx.channel.send(
                    embed=embed, file=file
                )  # here too

            self.response_time = time.time()

            try:
                msg: discord.Message = await self.ctx.bot.wait_for(
                    "message", check=self.text_input, timeout=self.timeout
                )

            ## Game timeout
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="\N{CLOCK FACE ONE OCLOCK} Game terminated",
                    description=f"{misc.space}players failed to respond within `{self.timeout//60}m`",
                    color=discord.Color.red(),
                )
                embed.add_field(
                    name="Stats",
                    value=f"{misc.space}country: `{self.country.names[0]}`\n{misc.space}capital: `{self.country.capital}`\n{misc.space}population: `{self.country.population:,} habitants`",
                    inline=False,
                )

                embed.set_thumbnail(url="attachment://flag.png")
                await self.game_msg.edit(embed=embed)  # no attachment edit requited
                return await self.end_game(self.ctx.channel)

            ## End (win)
            embed = discord.Embed(
                title=f"\N{PARTY POPPER} {self.country.names[0]} \N{PARTY POPPER}",
                description=f"{misc.space}{misc.curve} next in `10s`",
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
                userstats = f"{misc.space}accuracy : `{self.accuracy*100:.2f}%`\n{misc.space}time : `{time.time() - self.response_time:.2f}s`\n"
            else:
                ## End (skip)
                embed.title = f"\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR} {self.country.names[0]}"
                userstats = ""

            embed.add_field(
                name="Stats",
                value=f"{userstats}{misc.space}round : `{self.round} of {self.rounds}`\n\n{misc.space}capital: `{self.country.capital}`\n{misc.space}population: `{self.country.population:,} habitants`\n\n-# Game ID : #{self.id}",
                inline=False,
            )

            embed.set_author(
                name=msg.author.display_name, icon_url=msg.author.avatar.url
            )

            embed.set_thumbnail(url="attachment://flag.png")

            await self.game_msg.edit(embed=embed)  # no attachment required here either

            if self.round == self.rounds:
                return await self.end_game(self.ctx.channel)

            # Start next game in 10s
            if self.playing:
                async with interaction.channel.typing():
                    await asyncio.sleep(10.0)
