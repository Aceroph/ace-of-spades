import json
import pathlib
import re
import time
import datetime
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from games import CountryGuesser
from utils import misc, subclasses

if TYPE_CHECKING:
    from main import AceBot

directory = pathlib.Path(__file__).parent.parent  # ace-of-spades folder

TLD_REGEX = re.compile(r"^\.?([A-z]{2})$")

UTC_OFFSET_REGEX = re.compile(r"(?:UTC)?([+-])0*([1-9]*):0*([1-9]*)")

TIME_FORMAT = "%I:%M %p"   # 12-hour time format 

class Fun(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        super().__init__(
            bot=bot,
            emoji="\N{JIGSAW PUZZLE PIECE}",
        )

    @commands.group(invoke_without_command=True)
    async def games(self, ctx: commands.Context):
        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f"\N{VIDEO GAME} Game manager",
            description=f"{misc.curve} {ctx.channel.mention}",
        )
        games = [g for g in self.bot.games.values() if g.ctx.guild == ctx.guild]
        for game in games[:25]:
            embed.add_field(
                name=f"{misc.space}\n{game.title}",
                value=f"{misc.space}player: {game.gamemaster.mention}\n{misc.space}duration: `{misc.time_format(time.time()-game.START)}`\n{misc.space}id: `#{game.id}`",
            )

        if len(embed.fields) == 0:
            embed.set_footer(text="No games to be seen")

        return await ctx.reply(embed=embed, mention_author=False)

    @games.command(name="delete", aliases=["remove", "rm", "del"])
    @commands.has_permissions(manage_channels=True)
    async def game_delete(self, ctx: commands.Context, gameid: str):
        """Deletes the specified game
        This is not reversible !"""
        _id = gameid.removeprefix("#")
        if _id not in self.bot.games.keys():
            return await ctx.reply("Game not found !", delete_after=5, mention_author=False)

        self.bot.games.pop(_id)
        return await ctx.reply(f"Deleted game `{gameid}`", delete_after=15, mention_author=False)

    @commands.hybrid_command(aliases=["country", "cgssr"], invoke_without_command=True)
    async def countryguesser(self, ctx: commands.Context):
        """Starts a game of country guesser"""
        game = CountryGuesser(ctx)
        await game.send_menu()

    @commands.hybrid_command()
    async def cwiki(self, ctx: commands.Context, *, country: str):
        """Wiki for countries"""
        with open(directory / "games" / "countries.json", "r") as file:
            data: dict[str, Any] = json.load(file)

        def localize_tz(offset: str) -> str:
            """A hard-coded function to only on fixed type of string format
            Takes a utc_offset string as input (example: "UTC+08:30") and returns the corresponding time to the offset -> 12:24 PM 
            """
            sign, hrs, mins = UTC_OFFSET_REGEX.match(offset).groups()
            hrs = 0 if not hrs else int(sign + hrs)
            mins = 0 if not mins else int(mins)

            utcnow = discord.utils.utcnow()
            delta = datetime.timedelta(hours=hrs, minutes=mins)
            localized = utcnow.astimezone(tz=datetime.timezone(delta))
            return localized.strftime(TIME_FORMAT)

        async with ctx.channel.typing():
            matched = None
            tld = TLD_REGEX.sub(r"\g<1>", country)

            for country_dict in data:
                if (
                    country.casefold()
                    in (
                        country_dict["name"]["common"].casefold(),
                        country_dict["cca3"].casefold(),
                    )
                    or tld.casefold() == country_dict["cca2"].casefold()
                ):
                    matched = country_dict
                    break

            if matched is None:
                return await ctx.reply(content=f"No result found for `{country}`.", delete_after=5, mention_author=False)

            country = matched
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
            
            tzs = list(set((country['timezones'][0], country['timezones'][-1])))
            tzf = len(tzs) > 1
            local_time = list(map(localize_tz, tzs))
            ltf = len(local_time) > 1

            geo = [
                (
                    f"region: `{country['subregion']}` ({country['region']})"
                    if country.get("subregion")
                    else f"region: `{country['region']}`"
                ),
                f"timezone{'s'*tzf}: `{tzs[0]}` {f'to `{tzs[-1]}`'*tzf}",
                f"Local time: `{local_time[0]}` {f'to `{local_time[-1]}`'*ltf}",
                f"area: `{int(country['area']):,} km²`",
            ]

            gini = (
                f"gini index: `{list(country['gini'].values())[0]}` ({list(country['gini'])[0]})"
                if country.get("gini", None)
                else None
            )

            currency = (
                f"currency: `{country['currencies'][list(country['currencies'])[0]]['name']}` ({country['currencies'][list(country['currencies'])[0]]['symbol']})"
                if country.get("currencies", None)
                else None
            )

            embed = discord.Embed(
                title=f"{misc.info} {country['name']['official']}",
                description=f"{misc.curve} [view on map]({country['maps']['googleMaps']}) | [view on stree view]({country['maps']['openStreetMaps']})",
            )
            embed.set_thumbnail(url=country["flags"]["png"])

            embed.add_field(
                name="Endonyms",
                value=(
                    f"{misc.space}{native_names}\n"
                    f"{misc.space}{languages}\n"
                    f'{misc.space}{capital or "capital: `Unknown`"}'
                ),
                inline=False,
            )
            embed.add_field(
                name="Geography",
                value=misc.space + f"\n{misc.space}".join(geo),
                inline=False,
            )
            embed.add_field(
                name="Economy",
                value=(
                    f'{misc.space}{currency or "currency: `Unknown`"}\n'
                    f'{misc.space}{gini or "gini index: `Unknown`"}'
                ),
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
                    or ["demonyms: `Unknown`"]
                ),
                inline=False,
            )
            embed.add_field(
                name="Population",
                value=f"{misc.space}population: `{country['population']:,}` habitants",
                inline=False,
            )

        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Fun(bot))
