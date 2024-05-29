from utils import subclasses, misc
from typing import TYPE_CHECKING
from discord.ext import commands
from games import CountryGuesser
import requests
import discord

if TYPE_CHECKING:
    from main import AceBot


class Fun(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        super().__init__()
        self.emoji = "\N{JIGSAW PUZZLE PIECE}"
        self.bot = bot
    
    @commands.group(invoke_without_command=True)
    async def game(self, ctx: commands.Context):
        pass

    @game.command(name="delete", aliases=["remove", "rm", "del"])
    @commands.has_permissions(manage_channels=True)
    async def game_delete(self, ctx: commands.Context, gameid: str):
        """Deletes the specified game
        This is not reversible !"""
        if not gameid.strip("#") in self.bot.games.keys():
            return await ctx.reply("Game not found !", mention_author=False, delete_after=15)
        
        self.bot.games.pop(gameid.strip("#"))
        return await ctx.reply(f"Deleted game `#{gameid.strip("#")}`", mention_author=False, delete_after=15)


    @commands.hybrid_group(invoke_without_command=True, fallback="play")
    async def country(self, ctx: commands.Context):
        """Starts a game of country guesser"""
        if any([isinstance(game, CountryGuesser) for game in self.bot.games.values()]):
            await ctx.reply("An instance of that game is already in play !", mention_author=False, delete_after=15)
        else:
            game = CountryGuesser(ctx)
            self.bot.games[game.id] = game
            await game.send_menu()

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
