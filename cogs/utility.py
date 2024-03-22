from typing import Union, Callable, TYPE_CHECKING, Generator
from utils import subclasses, ui, misc
from discord.ext import commands
import unicodedata
import discord
import pathlib
import difflib
import arrow
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

    @commands.command(aliases=["char", "character"])
    async def charinfo(self, ctx: commands.Context, *, characters: str):
        fn: Callable[[str]] = lambda c: "%s : `%s` -> `\\N{%s}`" % (
            c,
            c.encode("unicode-escape"),
            unicodedata.name(c, "Found nothing"),
        )
        msg = "\n".join(map(fn, characters))
        await ctx.reply(msg)

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
            text=f"Query time : {(time.time()-timer)*1000:,.2f}ms",
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
        async with ctx.typing():
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

            # Number of commands, cogs, members, guilds, latency
            self.stats["#commands"] = len(self.bot.commands)
            self.stats["#modules"] = len(self.bot.cogs)
            self.stats["#guilds"] = len(self.bot.guilds)
            self.stats["#users"] = len(self.bot.users)
            self.stats["WS"] = self.bot.latency

    @commands.group(aliases=["stats", "about"], invoke_without_command=True)
    async def info(self, ctx: commands.Context):
        """Statistics for nerds"""
        if not hasattr(self, "stats"):
            embed = discord.Embed(
                title="Stats not found",
                description=">>> Gathering information..\nThis may take a few seconds",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed, mention_author=False, delete_after=5)
            await self.refresh_info(ctx)
        embed = discord.Embed(
            title="<:bot:1220186342361661470> " + self.bot.user.display_name,
            description=f"{misc.curve} is in `{self.stats['#guilds']}` servers, sees `{self.stats['#users']:,}` users",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Made by aceroph")
        embed.set_author(
            name="View source on github",
            url=misc.git_source(self.bot),
            icon_url="https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png",
        )
        # Basic info
        basic_info = "\n".join(
            sorted(
                [
                    f"created on: {discord.utils.format_dt(self.bot.user.created_at, 'd')}",
                    (
                        f"joined on: {discord.utils.format_dt(ctx.guild.me.joined_at, 'd')}"
                        if ctx.guild
                        else ""
                    ),
                    f"uptime: `{arrow.get(int(self.bot.boot)).humanize(only_distance=True)}`",
                ],
                key=lambda s: len(s),
                reverse=True,
            )
        )
        embed.add_field(
            name="About bot",
            value=f">>> {basic_info}",
            inline=False,
        )
        # Numbers !
        stats = "\n".join(
            sorted(
                [
                    f"lines of code: `{self.stats['lines']:,}`",
                    f"commands: `{self.stats['#commands']}`",
                    f"modules: `{self.stats['#modules']}`",
                    f"latency: `{self.stats['WS']*1000:.2f}ms`",
                ],
                key=lambda s: len(s),
                reverse=True,
            )
        )
        embed.add_field(
            name="Statistics",
            value=f">>> {stats}",
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
                    self.stats["total_cmds_ran"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key LIKE 'CMD_RAN:%';"
                        )
                    )[0]
                    self.stats["guild_cmds_ran"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key LIKE 'CMD_RAN:%' AND id = ?;",
                            (interaction.guild_id),
                        )
                    )[0]
                    self.stats["total_songs_played"] = (
                        await conn.fetchone(
                            "SELECT total(value) FROM statistics WHERE key = 'SONG_PLAYED';"
                        )
                    )[0]

            more_stats = "\n".join(
                sorted(
                    [
                        f"total commands ran: `{self.stats['total_cmds_ran']:.0f}`",
                        f"commands ran from guild: `{self.stats['guild_cmds_ran']:.0f}`",
                        f"total songs played: `{self.stats['total_songs_played']:.0f}`",
                    ],
                    key=lambda s: len(s),
                    reverse=True,
                )
            )
            embed = discord.Embed(color=discord.Color.blurple())
            embed.add_field(name="More statistics", value=f">>> {more_stats}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        show_more = discord.ui.Button(
            label="See more", style=discord.ButtonStyle.blurple
        )
        show_more.callback = info_show_more

        view = subclasses.View()
        view.add_item(show_more)
        view.add_quit(ctx.author, ctx.guild)

        await ctx.reply(embed=embed, mention_author=False, view=view)

    @info.command(name="refresh", aliases=["reload"])
    @commands.is_owner()
    async def info_refresh(self, ctx: commands.Context):
        """Refreshes all stats and information on the bot"""
        embed = discord.Embed(
            title="Reloading stats",
            description=">>> Gathering information..\nThis may take a few seconds",
            color=discord.Color.blurple(),
        )
        msg = await ctx.reply(embed=embed, mention_author=False)
        timer = time.time()
        await self.refresh_info(ctx)
        embed = discord.Embed(
            title="Done !",
            description=f">>> Refreshed stats\nTook {time.time()-timer:,.2f}s",
            color=discord.Color.blurple(),
        )
        await msg.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))
