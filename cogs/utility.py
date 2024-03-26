import asyncio
from typing import Union, TYPE_CHECKING, Generator
from utils import subclasses, ui, misc
from contextlib import redirect_stdout
from discord.ext import commands
from discord import app_commands
from cogs import errors
import unicodedata
import traceback
import textwrap
import discord
import pathlib
import difflib
import psutil
import zlib
import time
import io
import re

if TYPE_CHECKING:
    from main import AceBot


class SphinxObjectFileReader:
    BUFFER = 16 * 1024

    def __init__(self, buffer: bytes) -> None:
        self.stream = io.BytesIO(buffer)

    def readline(self) -> str:
        return self.stream.readline().decode()

    def skipline(self) -> None:
        self.stream.readline()

    def read_compressed_chunks(self) -> Generator[bytes, None, None]:
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFFER)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self) -> Generator[str, None, None]:
        buffer = b""
        for chunk in self.read_compressed_chunks():
            buffer += chunk
            position = buffer.find(b"\n")
            while position != -1:
                yield buffer[:position].decode()
                buffer = buffer[position + 1 :]
                position = buffer.find(b"\n")


class Utility(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        super().__init__()
        self.emoji = "\N{HAMMER AND WRENCH}"
        self.bot = bot
        self.RTFM_PAGES = {
            "stable": "https://discordpy.readthedocs.io/en/stable",
            "python": "https://docs.python.org/3/",
            "wavelink": "https://wavelink.dev/en/latest/",
        }

    def cog_load(self):
        self.bot.add_view(ui.PartyMenu(self.bot, {}))
        self.bot.logger.info(
            "Loaded persistent view %s from %s",
            ui.PartyMenu.__qualname__,
            self.qualified_name,
        )

    @commands.Cog.listener("on_voice_state_update")
    async def party_event(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        async with self.bot.pool.acquire() as conn:
            party_config = await conn.fetchone(
                "SELECT value FROM guildConfig WHERE id = :id AND key = :key;",
                {"id": member.id, "key": "party_id"},
            )

        if party_config:
            if not hasattr(self, "vcs"):
                self.vcs = {}

            name = member.name + "'s vc"
            if after.channel and after.channel.id in party_config:
                vc = await member.guild.create_voice_channel(
                    name=name, category=after.channel.category, bitrate=63000
                )
                self.vcs[str(vc.id)] = member.id
                await member.move_to(vc)

            if (
                before.channel
                and before.channel.bitrate == 63000
                and after.channel != before.channel
            ):
                if not before.channel.members:
                    await before.channel.delete()
                elif len(before.channel.members) == 1:
                    self.vcs[str(before.channel.id)] = before.channel.members[0].id

    @commands.guild_only()
    @commands.group(aliases=["vc", "voice"], invoke_without_command=True)
    async def party(self, ctx: commands.Context):
        """An all-in-one menu to configure your own voice channel"""
        vc = ctx.author.voice.channel if ctx.author.voice else None
        msg = ""
        if vc and vc.bitrate == 63000:
            menu = ui.PartyMenu(self.bot, self.vcs)
            await menu.check_ownership(ctx)

            await ctx.reply(
                msg,
                embed=ui.PartyMenu.Embed(ctx, self.vcs),
                view=ui.PartyMenu(self.bot, self.vcs),
            )
        elif vc:
            await ctx.reply(":warning: You are not in a party !")
        else:
            await ctx.reply(":warning: You are not in a vc !")

    @party.command(name="config")
    @commands.guild_only()
    @commands.is_owner()
    async def party_config(
        self, ctx: commands.Context, channel: Union[discord.VoiceChannel, int] = None
    ):
        """Sets the party lobby"""
        if channel:
            channel_id = (
                channel if type(channel) is int else channel.id or ctx.channel.id
            )
            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO guildConfig (id, key, value) VALUES (:id, :key, :value) ON CONFLICT(id, key) DO UPDATE SET value = :value WHERE id = :id AND key = :key;",
                    {"id": ctx.guild.id, "key": "party_id", "value": channel_id},
                )
            if isinstance(channel, discord.VoiceChannel):
                await ctx.send(f"Party lobby is now {channel.mention}")
            else:
                await ctx.send("Disabled party lobby")
        else:
            async with self.bot.pool.acquire() as conn:
                channel_id = await conn.fetchone(
                    "SELECT value FROM guildConfig WHERE id = :id AND key = :key;",
                    {"id": ctx.guild.id, "key": "party_id"},
                )
            channel = self.bot.get_channel(channel_id[1])
            await ctx.send(
                f"Current channel is {channel.mention if isinstance(channel, discord.VoiceChannel) else None}"
            )

    @commands.hybrid_command(aliases=["char", "character"])
    @app_commands.describe(characters="The characters to get info on")
    async def charinfo(self, ctx: commands.Context, *, characters: str):
        """Gets information on one or multiple characters
        Supports discord emojis, emojis, numbers and any other character !

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
            characters = characters.replace(num, chr(int(num)))

        for char in characters:
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
            title=f"Converted {len(results)} character{'s' if len(results) > 1 else ''}",
            description="\n".join(
                [
                    f"[{c[0]}] {c[2]} #{ord(c[0]) if len(c[0]) == 1 else 0}```\n{c[1]}```"
                    for c in results
                ]
            ),
            color=discord.Color.blurple(),
        )

        await ctx.reply(embed=embed, mention_author=False)

    def parse_object_inv(
        self, stream: SphinxObjectFileReader, url: str
    ) -> dict[str, str]:
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result: dict[str, dict[str, str]] = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != "# Sphinx inventory version 2":
            raise RuntimeError("Invalid objects.inv file version.")

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        _ = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if "zlib" not in line:
            raise RuntimeError("Invalid objects.inv file, not z-lib compatible.")

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r"(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)")
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, _, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(":")
            if directive == "py:module" and name in result:
                continue

            if directive == "std:doc":
                subdirective = "label"

            if location.endswith("$"):
                location = location[:-1] + name

            key = name if dispname == "-" else dispname
            prefix = f"{subdirective}:" if domain == "std" else ""

            if projname == "discord.py":
                key = key.replace("discord.ext.commands.", "").replace("discord.", "")

            result[f"{prefix}{key}"] = {
                "url": "/".join((url, location)),
                "type": directive.split(":")[1],
            }

        return result

    async def build_rtfm_table(self):
        # Build cache
        cache: dict[str, dict[str, dict[str, str]]] = {}
        for key, page in self.RTFM_PAGES.items():
            cache[key] = {}
            # Get objects.inv from docs
            async with self.bot.session.get(page + "/objects.inv") as resp:
                if resp.status != 200:
                    raise RuntimeError("Failed")

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache

    async def do_rtfm(
        self, ctx: commands.Context, key: str = "stable", obj: str = None
    ):
        if obj is None:
            await ctx.send(self.RTFM_PAGES[key])
            return

        timer = time.time()
        # If no cache
        if not hasattr(self, "_rtfm_cache"):
            await ctx.typing()
            await self.build_rtfm_table()

        # Discard any discord.ext.commands
        obj = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", obj)

        cache = list(self._rtfm_cache[key].items())

        # Sort and get the top 6 items
        matches = sorted(
            cache,
            key=lambda c: difflib.SequenceMatcher(None, obj, c[0]).ratio(),
            reverse=True,
        )[:5]

        embed = discord.Embed(
            title=f"RTFM - {'Discord.py' if key == 'stable' else key.capitalize()}",
            colour=discord.Colour.blurple(),
        )
        embed.set_footer(
            text=f"Query time : {(time.time()-timer):,.2f}s",
            icon_url=ctx.author.avatar.url,
        )
        if len(matches) == 0:
            return await ctx.send("Could not find anything. Sorry.")

        # Format results
        results = []
        for key, data in matches:
            results.append(f"[`{data['type'][:4]}`] [`{key}`]({data['url']})")

        embed.description = "\n".join(results)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.group(invoke_without_command=True, aliases=["rtfd"])
    async def rtfm(self, ctx: commands.Context, obj: str = None):
        """Read The Fucking Manual
        Will fetch discord.py docs for the specifed object"""
        await self.do_rtfm(ctx, obj=obj)

    @rtfm.command(name="py", aliases=["python"])
    async def rtfm_py(self, ctx: commands.Context, obj: str = None):
        """Read The Fucking Manual
        Will fetch python docs for the specifed object"""
        await self.do_rtfm(ctx, key="python", obj=obj)

    @rtfm.command(name="wavelink", aliases=["wl"])
    async def rtfm_wavelink(self, ctx: commands.Context, obj: str = None):
        """Read The Fucking Manual
        Will fetch wavelink docs for the specifed object"""
        await self.do_rtfm(ctx, key="wavelink", obj=obj)

    async def refresh_info(self, ctx: commands.Context):
        async with ctx.channel.typing():
            self.stats = {}
            # Total lines of code
            self.stats["lines"] = 0
            root = pathlib.Path(__file__).parent.parent
            for file in pathlib.Path(__file__).parent.parent.glob("**/*"):
                if file.name.endswith((".py", ".json")) and not any(
                    file.is_relative_to(bad) for bad in root.glob("**/.*")
                ):
                    with open(file, "r") as f:
                        self.stats["lines"] += len(f.readlines())

            self.stats["#commands"] = len(self.bot.commands)
            self.stats["#modules"] = len(self.bot.cogs)
            self.stats["#guilds"] = len(self.bot.guilds)
            self.stats["#users"] = len(self.bot.users)

            process = psutil.Process()
            self.stats["pid"] = process.pid
            self.stats["mem"] = process.memory_full_info().rss / 1024**2
            self.stats["mem%"] = process.memory_percent()
            self.stats["cpu%"] = process.cpu_percent()

    @commands.hybrid_command(aliases=["stats", "about"], invoke_without_command=True)
    async def info(self, ctx: commands.Context):
        """Statistics for nerds"""
        if not hasattr(self, "stats"):
            embed = discord.Embed(
                title=f"{misc.dislike} Stats not found",
                description=">>> Gathering information..\nThis may take a few seconds",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed, mention_author=False, delete_after=5)
            await self.refresh_info(ctx)

        embed = discord.Embed(
            title=self.bot.user.display_name,
            description=f"{misc.space}{misc.server}servers: `{self.stats['#guilds']}`\n{misc.space}{misc.members}users: `{self.stats['#users']:,}`",
            color=discord.Color.blurple(),
        )
        embed.set_footer(
            text=f"Made by aceroph using discord.py v{discord.__version__}",
            icon_url=misc.python,
        )
        embed.set_author(
            name="View source on github",
            url=misc.git_source(self.bot),
            icon_url=misc.github,
        )

        embed.add_field(
            name="Timestamps",
            value=f"{misc.space}created on: {discord.utils.format_dt(self.bot.user.created_at, 'd')}\
            \n{misc.space}joined on: {discord.utils.format_dt(ctx.guild.me.joined_at, 'd') if ctx.guild else '`never.`'}\
            \n{misc.space}uptime: `{misc.time_format(time.time()-self.bot.boot)}`",
            inline=False,
        )
        embed.add_field(
            name=f"Code statistics",
            value=f"{misc.space}lines of code: `{self.stats['lines']:,}`\
            \n{misc.space}commands: `{self.stats['#commands']}`\
            \n{misc.space}modules: `{self.stats['#modules']}`",
            inline=False,
        )
        embed.add_field(
            name="Process",
            value=f"{misc.space}pid: `{self.stats['pid']}`\
                    \n{misc.space}cpu: `{self.stats['cpu%']:.1f}%`\
                    \n{misc.space}mem: `{self.stats['mem']:,.1f}MB` (`{self.stats['mem%']:.1f}%`)",
            inline=False,
        )

        # UI
        async def info_show_more(interaction: discord.Interaction):
            # Fetch more stats if non existant or its been more that 5 minutes
            if (
                not "last_updated" in self.stats.keys()
                or time.time() - self.stats["last_updated"] >= 300
            ):
                async with self.bot.pool.acquire() as conn:
                    self.stats["last_updated"] = time.time()

                    # COMMANDS STATS
                    self.stats["total_cmds_ran"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key LIKE 'CMD_RAN:%';"
                        )
                    )[0]
                    self.stats["guild_cmds_ran"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key LIKE 'CMD_RAN:%' AND id = ?;",
                            (interaction.guild_id or 0),
                        )
                    )[0]

                    # MUSIC STATS
                    self.stats["total_songs_played"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYED';"
                        )
                    )[0]
                    self.stats["guild_songs_played"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYED' AND id = ?;",
                            (interaction.guild_id),
                        )
                    )[0]
                    self.stats["total_playtime"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYTIME';"
                        )
                    )[0]
                    self.stats["guild_playtime"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYTIME' AND id = ?;",
                            (interaction.guild_id),
                        )
                    )[0]

                    # TOP COMMANDS
                    self.stats["top_guild_commands"] = await conn.fetchall(
                        "SELECT key, value FROM statistics WHERE key LIKE 'CMD_RAN:%' AND id = ? ORDER BY value DESC LIMIT 5;",
                        (interaction.guild_id or 0),
                    )

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
                    for i, cmd in enumerate(self.stats["top_guild_commands"])
                ]
            )

            embed = discord.Embed(color=discord.Color.blurple())
            embed.add_field(
                name="Top commands",
                value=f"{misc.space}{top_commands}\n\n{misc.space}Total ran: `{self.stats['total_cmds_ran']:.0f}`\
                \n{misc.space}{misc.curve} from {'guild' if interaction.guild else 'DMs'}: `{self.stats['guild_cmds_ran']:.0f}`",
            )
            embed.add_field(
                name="Music statistics",
                value=f"{misc.space}Total songs played: `{self.stats['total_songs_played']:.0f}`\
                \n{misc.space}{misc.curve} from guild: `{self.stats['guild_songs_played']:.0f}`\
                \n\n{misc.space}Total playtime: `{misc.time_format(self.stats['total_playtime'])}`\
                \n{misc.space}{misc.curve} from guild: `{misc.time_format(self.stats['guild_playtime'])}`",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        async def refresh_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.bot.owner_id:
                raise errors.NotYourButton("Only the owner can refresh stats manually")

            embed = discord.Embed(
                title="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS} Reloading stats",
                description=">>> Gathering information..\nThis may take a few seconds",
                color=discord.Color.blurple(),
            )
            await interaction.response.edit_message(
                embed=embed, view=None, delete_after=5
            )
            await self.refresh_info(ctx)
            await self.info(ctx)

        show_more = discord.ui.Button(
            label="See more", style=discord.ButtonStyle.blurple
        )
        show_more.callback = info_show_more

        refresh = discord.ui.Button(label="Refresh")
        refresh.callback = refresh_callback

        view = subclasses.View()
        view.add_item(show_more)
        view.add_item(refresh)
        view.add_quit(ctx.author, ctx.guild)

        if ctx.interaction:
            await ctx.interaction.channel.send(embed=embed, view=view)
        else:
            await ctx.reply(embed=embed, mention_author=False, view=view)

    @commands.command(aliases=["py"])
    @commands.is_owner()
    async def python(self, ctx: commands.Context, *, body: str = None):
        """Evaluates code"""

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "msg": ctx.message,
            "_": getattr(self, "_last_result", None),
        }

        env.update(globals())

        # If no body, use reference, else cry ab it
        if not body:
            try:
                if ctx.message.reference:
                    pos = ctx.message.reference.resolved.content.find(ctx.invoked_with)
                    body = ctx.message.reference.resolved.content[pos + 3 :]
            except Exception as err:
                await ctx.message.add_reaction(misc.no)
                return await ctx.reply(
                    f"Failed to find any executable : {err}",
                    mention_author=False,
                    delete_after=10,
                )

        # Get rid of codeblocks
        if body.lstrip().startswith("```") and body.lstrip().endswith("```"):
            body = "\n".join(body.split("\n")[1:-1])

        stdout = io.StringIO()

        # Make function
        to_compile = f"async def func():\n"
        for line in body.split("\n"):
            if len(line.strip()) == 0:
                continue

            # Always return value
            if line == body.split("\n")[-1]:
                if not line.lstrip(" ").startswith(("return", "print")):
                    indent = len(line) - len(line.lstrip(" "))
                    to_compile += " " * (indent + 2) + "return " + line + "\n"
                    break

            to_compile += " " * 2 + line + "\n"

        # Add function to globals
        try:
            exec(to_compile, env)
        except Exception:
            try:
                await ctx.message.add_reaction(misc.no)
            except:
                pass

            # If user reacts, send error
            try:
                await self.bot.wait_for(
                    "reaction_add",
                    check=lambda _, u: u == ctx.author,
                    timeout=30,
                )

                embed = discord.Embed(
                    title=":warning: Failed to compile",
                    description=f"```py\n{misc.clean_traceback(traceback.format_exc())}```",
                    color=discord.Color.red(),
                )
                embed.set_author(
                    name=ctx.author.display_name, icon_url=ctx.author.avatar.url
                )
                view = subclasses.View()
                view.add_quit(
                    style=discord.ButtonStyle.gray,
                    delete_reference=False,
                    author=ctx.author,
                    emoji=misc.delete,
                    guild=ctx.guild,
                    label=None,
                )
                return await ctx.reply(embed=embed, mention_author=False, view=view)
            except asyncio.TimeoutError:
                return

        func = env["func"]

        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            try:
                await ctx.message.add_reaction(misc.no)
            except:
                pass

            # If user reacts, send error
            try:
                await self.bot.wait_for(
                    "reaction_add",
                    check=lambda _, u: u == ctx.author,
                    timeout=30,
                )
                value = stdout.getvalue()
                embed = discord.Embed(
                    title=f":warning: Failed to evaluate",
                    description=f"```py\n{value}{misc.clean_traceback(traceback.format_exc())}```",
                    color=discord.Color.red(),
                )
                view = subclasses.View()
                view.add_quit(
                    style=discord.ButtonStyle.gray,
                    delete_reference=False,
                    author=ctx.author,
                    emoji=misc.delete,
                    guild=ctx.guild,
                    label=None,
                )
                return await ctx.reply(embed=embed, mention_author=False, view=view)
            except asyncio.TimeoutError:
                return

        value = stdout.getvalue()
        try:
            await ctx.message.add_reaction(misc.yes)
        except:
            pass

        # Buttons
        view = subclasses.View()
        view.add_quit(
            style=discord.ButtonStyle.gray,
            delete_reference=False,
            author=ctx.author,
            emoji=misc.delete,
            guild=ctx.guild,
            label=None,
        )

        if ret is None:
            if value:
                await ctx.reply(f"```py\n{value}\n```", mention_author=False, view=view)
        else:
            self._last_result = ret
            await ctx.reply(
                f"```py\n{value}{ret}\n```", mention_author=False, view=view
            )


async def setup(bot):
    await bot.add_cog(Utility(bot))
