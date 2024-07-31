import json
import re
import string
import time
import unicodedata
from typing import TYPE_CHECKING, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from ext import embedbuilder, info, rtfm
from utils import misc, subclasses

if TYPE_CHECKING:
    from main import AceBot


class Utility(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        super().__init__(
            bot=bot,
            emoji="\N{HAMMER AND WRENCH}",
        )

    @commands.hybrid_command(aliases=["char", "character"])
    @app_commands.describe(characters="The characters to get info on")
    async def charinfo(self, ctx: commands.Context, *, characters: str):
        """Gets information on one or multiple characters
        Supports discord emojis, emojis, numbers and any special character !

        P.S.
        {curve} Numbers must be seperated with spaces"""

        results = []
        i: int = 0
        # Process discord-only emojis first
        discord_emojis: list[str] = re.findall(r"<:\w+:\d+>", characters)
        for emoji in discord_emojis:
            characters = characters.replace(emoji, "")
            results.append([emoji, emoji, emoji.split(":")[1]])

        # Check for numbers to convert
        numbers: list[int] = re.findall(r"\d+", characters)
        for num in numbers:
            characters = characters.replace(
                num, chr(int(num)) if int(num) >= 161 and int(num) <= 55291 else ""
            )

        for char in characters:
            if char in string.ascii_letters:
                continue

            name = r"\N{%s}" % unicodedata.name(char, "EXTREMELY RARE ERROR")

            if ord(char) == 32:
                continue

            # If VARIATION SELECTOR
            if ord(char) == 65039:
                results[i - 1][1] += name
                continue

            unicode = (
                str(char.encode("unicode-escape")).strip("b'\\u").strip("0").strip("U")
            )
            url = f"[\\U{unicode}](https://www.fileformat.info/info/unicode/char/{unicode}/index.htm)"
            results.append([char, name, url])

            i += 1

        embed = discord.Embed(
            description="\n".join(
                [
                    f"[{c[0]}] {c[2]} #{ord(c[0]) if len(c[0]) == 1 else 0}```\n{c[1]}```"
                    for c in results
                ]
            )
            or "Nothing to convert",
            color=discord.Color.blurple(),
        )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(aliases=["rtfd"])
    @app_commands.describe(source="From where to gather docs", obj="What to search for")
    async def rtfm(
        self,
        ctx: commands.Context,
        source: Optional[Literal[tuple(rtfm.literal_rtfm)]] = ("stable"),  # type: ignore
        obj: str = None,
    ):
        """Read The Fucking Manual
        Will fetch discord.py docs for the specifed object"""
        for src, _ in rtfm.RTFM_PAGES.items():
            if source in src:
                await rtfm.do_rtfm(ctx, key=src, obj=obj)

    @rtfm.autocomplete("source")
    async def rtfm_autocomplete(self, interaction: discord.Interaction, current: str):
        return sorted(
            [
                app_commands.Choice(name=source[0].capitalize(), value=source)
                for source, _ in rtfm.RTFM_PAGES.items()
                if current.casefold() in source or len(current) == 0
            ],
            key=lambda c: c.name,
        )[:25]

    @commands.hybrid_command(
        name="info", aliases=["stats", "about"], invoke_without_command=True
    )
    async def _info(self, ctx: commands.Context):
        """Statistics for nerds
        Anyone can refresh stats every 5 minutes"""
        view = info.InfoView(self.bot, ctx.author)
        # view.add_quit(ctx.author, ctx.guild)
        embed = await view.embed(ctx)
        return await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="eval")
    @app_commands.describe(
        language="The language to run the code with", body="The code to run"
    )
    async def _eval(
        self,
        ctx: commands.Context,
        language: Optional[str] = None,
        *,
        body: str,
    ):
        """Runs code in the specified language, aliases work too !"""

        # Get language
        if not language in misc.literal_runtimes:
            language = (
                language + " " if language else ""
            )  # Fix language being none in some cases
            body = language + body
            language = "python"

        # Clean body
        body = misc.clean_codeblock(body)

        # Convert language
        for r in misc.runtimes:
            if (
                language.casefold() == r["language"]
                or language.casefold() in r["aliases"]
            ):
                language = r
                break

        # Format code if python
        if language["language"] == "python":
            code = "import asyncio\nasync def func():\n"
            for i, line in enumerate(body.splitlines()):
                if len(line.strip()) == 0:
                    continue

                if i == len(body.splitlines()) - 1:
                    if not any(
                        [
                            line.strip().startswith(
                                ("print", "raise", "import", "return")
                            ),
                            "=" in line,
                        ]
                    ):
                        code += " " * 2 + f"print({line})\n"
                        continue

                code += " " * 2 + line + "\n"

            body = code + "asyncio.run(func())"

        payload = {
            "language": language["language"],
            "version": language["version"],
            "files": [{"content": body}],
        }
        response = await (
            await self.bot.session.post(
                "https://emkc.org/api/v2/piston/execute", data=json.dumps(payload)
            )
        ).json()

        output = response["run"]["output"] or "No output"

        await subclasses.reply(
            ctx,
            output,
            prefix=f"```{language['language']}\n",
            suffix="```",
            mention_author=False,
        )

        if not ctx.interaction:
            if response["run"]["code"] != 0:
                await ctx.message.add_reaction(misc.no)
            else:
                await ctx.message.add_reaction(misc.yes)

    @_eval.autocomplete("language")
    async def eval_autocomplete(self, interaction: discord.Interaction, current: str):
        # Avoid repetition
        names = set(
            r["language"]
            for r in misc.runtimes
            if current.casefold() in r["language"] or len(current) == 0
        )
        return sorted(
            [app_commands.Choice(name=n.capitalize(), value=n) for n in names],
            key=lambda c: c.name,
        )[:25]

    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context):
        """Simplest command, ping \N{TABLE TENNIS PADDLE AND BALL}"""
        embed = discord.Embed(
            title="Pong \N{TABLE TENNIS PADDLE AND BALL}",
            description=f">>> WS: `{round(self.bot.latency * 1000)}ms`",
            color=discord.Color.blurple(),
        )
        return await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command()
    async def embed(self, ctx: commands.Context, *, source=None):
        """Create, export and import rich embeds.
        Embeds are exported in a JSON format which can be used to import embeds or even be used in tags.
        """
        # Import embed
        if source:
            # Import from message id
            if re.fullmatch(r"[0-9]+", source):
                try:
                    message = await ctx.channel.fetch_message(int(source))
                except commands.MessageNotFound:
                    return await ctx.reply(
                        "Unknown message, make sure it is from this channel.\nYou can always export your embeds and import them directly.",
                        mention_author=False,
                    )
                embed = message.embeds[0]
                builder = embedbuilder.EmbedBuilder(
                    embed=embed, bot=self.bot, author=ctx.author, imported=True
                )
                return await builder.start(ctx)

            # Import from json dict
            elif re.fullmatch(r"{.*}", misc.clean_codeblock(source), flags=re.S):
                embed = discord.Embed.from_dict(
                    json.loads(misc.clean_codeblock(source))
                )
                builder = embedbuilder.EmbedBuilder(
                    embed=embed, bot=self.bot, author=ctx.author, imported=True
                )
                return await builder.start(ctx)

        # Base embed
        embed = discord.Embed(
            title="Title (256 characters), can lead to a url if given",
            description="Description (4096 characters)\nThe sum of all characters cannot exceed 6000, any field left unedited will disappear",
            color=discord.Color.blurple(),
            url="https://google.com/",
        )
        embed.set_author(
            name="Author name (256 characters), can lead to a url if given",
            icon_url="https://archive.org/download/discordprofilepictures/discordblue.png",
            url="https://google.com/",
        )
        embed.set_footer(
            text="Footer (2048 characters), only supports emojis and other characters",
            icon_url="https://archive.org/download/discordprofilepictures/discordblue.png",
        )
        embed.set_thumbnail(
            url="https://archive.org/download/discordprofilepictures/discordblue.png"
        )
        embed.set_image(
            url="https://archive.org/download/discordprofilepictures/discordblue.png"
        )
        embed.add_field(
            name="Field title (256 characters)",
            value="Supports all kinds of markdown unlike titles who only supports emojis and other characters, a maximum of 25 fields is allowed",
            inline=False,
        )
        embed.add_field(
            name="Hyperlinks",
            value="Areas who support markdowns also support [hyperlinks](https://google.com/)",
            inline=True,
        )
        embed.add_field(
            name="Inline fields",
            value="Fields can also be inlined with others. (1024 characters)",
            inline=True,
        )

        builder = embedbuilder.EmbedBuilder(embed=embed, bot=self.bot)
        return await builder.start(ctx)


async def setup(bot):
    await bot.add_cog(Utility(bot))
