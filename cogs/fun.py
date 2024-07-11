from utils import subclasses, misc
from typing import TYPE_CHECKING, Any
from discord.ext import commands
from games import CountryGuesser
import pathlib
import discord
import json
import re


if TYPE_CHECKING:
    from main import AceBot

directory = pathlib.Path(__file__).parent.parent   # ace-of-spades folder
    

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
        with open(directory / "games" / "countries.json", 'r') as file:
            data: dict[str, Any] = json.load(file)
            
        async with ctx.channel.typing():
            matched = None
            tld_pattern = r'^\.?([A-z]{2})$'
            tld = re.sub(tld_pattern, '.\\1', country)   
    
            for country_dict in data:
                if (country.casefold() in (country_dict['name']['common'].casefold(), country_dict['cca3'].casefold())
                    or tld.casefold() in country_dict['tld']):
                    matched = country_dict
                    break
                    
            if matched is None:
                return await ctx.send(content=f'No result found for `{country}`.')
                
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

            geo = [
                f"region: `{country['subregion']}` ({country['region']})" if country.get("subregion") else f"region: `{country['region']}`",
                f"timezones: `{country['timezones'][0]}` to `{country['timezones'][-1]}`",
                f"area: `{int(country['area']):,} km²`",
            ]

            gini = (
                f"gini index: `{list(country['gini'].values())[0]}` ({list(country['gini'])[0]})"
                if country.get("gini", None)
                else None
            )

            currency = f"currency: `{country['currencies'][list(country['currencies'])[0]]['name']}` ({country['currencies'][list(country['currencies'])[0]]['symbol']})" if country.get("currencies", None) else None

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
                + (currency or "currency: `Unknown`")
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
                    ] or ["unknown demonyms"]
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
