import traceback
from cogs.errors import NoVoiceFound, PlayerConnectionFailure
from typing import TYPE_CHECKING, cast, Union
from utils import subclasses, misc
from discord.ext import commands
from tabulate import tabulate
import wavelink
import textwrap
import discord
import re

if TYPE_CHECKING:
    from main import AceBot


class Music(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        super().__init__()
        self.bot = bot
        self.emoji = "\N{MUSICAL NOTE}"
        self.home: discord.TextChannel = None
        self.nodes: dict[str, wavelink.Node] = None
        self.config = bot.config["wavelink"]

    async def connection(self):
        nodes = [
            wavelink.Node(
                uri=self.config["uri"],
                password=self.config["passwd"],
                inactive_player_timeout=180,
                resume_timeout=300,
                retries=5,
            )
        ]
        self.nodes = await wavelink.Pool.connect(
            nodes=nodes, client=self.bot, cache_capacity=100
        )

    async def cog_load(self):
        await self.connection()

    def clean_title(self, track: wavelink.Playable):
        regexes = [
            r"[\[\(][A-z0-9\s]*[\]\)]",
            r"[^a-zA-Z0-9\s\\\/]",
            track.author,
            r"[[:punct:]] ",
        ]
        clean: str = track.title
        matches = (
            re.findall(pattern=regex, string=clean, flags=re.IGNORECASE)
            for regex in regexes
        )
        for x in matches:
            for y in x:
                clean = clean.replace(y, "")

        return clean

    async def now_playing_logic(
        self, origin: Union[commands.Context, wavelink.TrackStartEventPayload]
    ):
        player = origin.player
        if hasattr(player, "silent"):
            if player.silent:
                return

        # Formatting
        track: wavelink.Playable = (
            origin.original if hasattr(origin, "original") else player.current
        )
        clean_title = self.clean_title(track)

        length = f"{track.length//60000}:{format(track.length//1000 % 60, '02d')}"
        current_time = (
            f"{player.position//60000}:{format(player.position//1000 % 60, '02d')}"
        )
        bar_length = max(int(len(clean_title) // 1.5) - 6, 20)
        fraction = int(player.position / track.length * bar_length)

        progress_bar = (
            f"\n\n```\n{current_time} [{fraction * '='}{(bar_length - fraction) * '-'}] {length}```"
            if isinstance(origin, commands.Context)
            else ""
        )
        embed = discord.Embed(
            title="Now Playing",
            description=f"\N{MUSICAL SYMBOL EIGHTH NOTE} {clean_title}\n{misc.curve} by `{track.author}`"
            + progress_bar,
            color=discord.Color.blurple(),
        )

        if track.recommended:
            embed.set_footer(text=f"Recommended by {track.source}")
        else:
            embed.set_footer(
                text=f"Requested by {track.extras.name or None}",
                icon_url=track.extras.icon_url or None,
            )

        embed.set_thumbnail(url=track.artwork or track.album.url)

        if isinstance(origin, commands.Context):
            await origin.reply(embed=embed, mention_author=False)
        else:
            await self.home.send(embed=embed)

    async def get_player(self, ctx: commands.Context) -> None:
        if not self.home:
            self.home = ctx.channel

        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            raise NoVoiceFound

        ctx.player = player
        return await super().cog_before_invoke(ctx)

    @subclasses.Cog.listener()
    async def on_wavelink_node_ready(
        self, payload: wavelink.NodeReadyEventPayload
    ) -> None:
        self.bot.logger.info(
            f"Wavelink node connected: {payload.node!r} | Resumed: {payload.resumed}"
        )

    @subclasses.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player) -> None:
        if self.home:
            await self.home.send(
                f"The player has been inactive for `{player.inactive_timeout}` seconds."
            )
        await player.disconnect()

    @subclasses.Cog.listener()
    async def on_wavelink_track_exception(
        self, payload: wavelink.TrackExceptionEventPayload
    ) -> None:
        print(payload.exception)

    @subclasses.Cog.listener()
    async def on_wavelink_track_start(
        self, payload: wavelink.TrackStartEventPayload
    ) -> None:
        async with self.bot.pool.acquire() as conn:
            is_silent: bool = await conn.fetchone(
                "SELECT value FROM guildConfig WHERE id = ? AND key = 'silent';",
                (payload.player.guild.id),
            )

            # +1 song played
            await conn.execute(
                "INSERT INTO statistics (id, key, value) VALUES (?, ?, 1) ON CONFLICT(id, key) DO UPDATE SET value = value + 1;",
                (
                    payload.player.guild.id,
                    "SONG_PLAYED",
                ),
            )
            # add length of track
            await conn.execute(
                "INSERT INTO statistics (id, key, value) VALUES (:id, :key, :value) ON CONFLICT(id, key) DO UPDATE SET value = value + :value;",
                {
                    "id": payload.player.guild.id,
                    "key": "SONG_PLAYTIME",
                    "value": payload.track.length // 1000,
                },
            )
            await conn.commit()

        if not is_silent:
            return await self.now_playing_logic(payload)

    @commands.group()
    @commands.is_owner()
    async def lavalink(self, ctx: commands.Context) -> None:
        node = (
            cast(wavelink.Player, ctx.voice_client).node
            if ctx.voice_client
            else [node for node in self.nodes.values()][0]
        )
        info = await node.fetch_info()

        sources = "\n - " + "\n - ".join(info.source_managers)
        plugins = "\n - " + "\n - ".join(
            [f"{plg.name} ({plg.version})" for plg in info.plugins]
        )
        msg = f"```\nstatus: {node.status}\n\njvm: {info.jvm}\nlavaplayer: {info.lavaplayer}\nwavelink: {wavelink.__version__}\n\nsources:{sources}\n\nplugins: {plugins if len(info.plugins) > 0 else 'none'}```"
        await ctx.reply(msg, mention_author=False)

    @commands.guild_only()
    @commands.before_invoke(get_player)
    @commands.command(aliases=["np", "now"])
    async def nowplaying(self, ctx: commands.Context) -> None:
        return await self.now_playing_logic(ctx)

    @commands.guild_only()
    @commands.command(aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a song with the given query."""
        player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)  # type: ignore
            except AttributeError:
                raise NoVoiceFound
            except discord.ClientException:
                raise PlayerConnectionFailure()

        if not hasattr(ctx, "player"):
            ctx.player = player

        # Autoplay
        player.autoplay = wavelink.AutoPlayMode.enabled

        tracks: wavelink.Search = await wavelink.Playable.search(query)
        if not tracks:
            await ctx.reply(
                f"{ctx.author.mention} - Could not find any tracks with that query. Please try again.",
                mention_author=False,
            )
            return

        # Where the bot sends announcements
        self.home = ctx.channel

        if isinstance(tracks, wavelink.Playlist):
            # Add requested user to tracks
            for track in tracks.tracks:
                track.extras = {
                    "name": ctx.author.display_name,
                    "icon_url": ctx.author.display_avatar.url,
                }

            added: int = await player.queue.put_wait(tracks)

            length = sum([t.length // 1000 for t in tracks.tracks])
            length_fmt = f"{length//3600}h{format(length//60 % 60, '02d')}m{format(length % 60, '02d')}s"

            embed = discord.Embed(
                title="Added playlist to queue",
                description=f"\N{MUSICAL SYMBOL EIGHTH NOTE} loaded `{added}` songs from `{tracks.name}`\n{misc.curve}total length: {length_fmt}",
            )
            await ctx.reply(embed=embed, mention_author=False)

        else:
            # Add requested user to track
            track: wavelink.Playable = tracks[0]
            track.extras = {
                "name": ctx.author.display_name,
                "icon_url": ctx.author.display_avatar.url,
            }

            await player.queue.put_wait(track)
            embed = discord.Embed(
                title="Added song to queue",
                description=f"\N{MUSICAL SYMBOL EIGHTH NOTE} {self.clean_title(track)}\n{misc.curve} by `{track.author}`",
            )
            await ctx.reply(embed=embed, mention_author=False)

        if not player.playing:
            await player.play(player.queue.get(), volume=30)

    @commands.command()
    @commands.guild_only()
    @commands.before_invoke(get_player)
    async def queue(self, ctx: commands.Context):
        """Lists the next titles and position in the queue"""

        length = len(ctx.player.queue._items)
        if length > 0:
            paginator = subclasses.Paginator(
                ctx=ctx,
                embed=discord.Embed(
                    title=f"Queue ({str(length) + ' songs' if length > 1 else str(length) + ' song'})",
                    color=discord.Color.blurple(),
                ),
                max_lines=20,
                prefix="```",
                suffix="```",
            )
            items = [
                [
                    format(i + 1, "02d"),
                    textwrap.shorten(
                        track.title, 45, break_long_words=False, placeholder="..."
                    ),
                ]
                for i, track in enumerate(ctx.player.queue._items)
            ]
            pages = [items[p : p + 20] for p in range(0, len(items), 20)]

            for page in pages:
                table = tabulate(
                    headers=["No#", "Track"],
                    tabular_data=page,
                    tablefmt="outline",
                    stralign="left",
                    numalign="left",
                )
                paginator.add_page(table)

            await paginator.start()
        else:
            await ctx.reply("Queue empty !", mention_author=False)

    @commands.command()
    @commands.guild_only()
    @commands.before_invoke(get_player)
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the current player's queue"""

        length = len(ctx.player.queue._items)
        if length > 1:
            ctx.player.queue.shuffle()
            embed = discord.Embed(
                title="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS} Shuffled queue",
                description=f">>> reordered {length} items",
                color=discord.Color.blurple(),
            )
        else:
            embed = discord.Embed(
                title="\N{CROSS MARK} Did not shuffle queue",
                description=f"> why shuffle {length + ' item' if length > 0 else 'nothing'}?",
            )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command()
    @commands.guild_only()
    @commands.before_invoke(get_player)
    async def pause(self, ctx: commands.Context):
        """Pauses or resumes activity"""

        await ctx.player.pause(not ctx.player.paused)
        if not ctx.player.paused:
            embed = discord.Embed(
                title="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16} Resumed player",
                description=f"{misc.curve} to pause, run the command again",
                color=discord.Color.blurple(),
            )
        else:
            embed = discord.Embed(
                title="\N{DOUBLE VERTICAL BAR}\N{VARIATION SELECTOR-16} Paused player",
                description=f"{misc.curve} to resume, run the command again",
                color=discord.Color.blurple(),
            )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.guild_only()
    @commands.command(aliases=["next"])
    @commands.before_invoke(get_player)
    async def skip(self, ctx: commands.Context):
        """Skips the current song"""

        await ctx.player.skip()
        await ctx.reply("Skipped song", mention_author=False)

    @commands.guild_only()
    @commands.command(aliases=["quit"])
    @commands.before_invoke(get_player)
    async def stop(self, ctx: commands.Context):
        """Stops playing music and disconnects the player"""

        await ctx.player.disconnect()
        await ctx.reply("Stopped playing music", mention_author=False)

    @commands.command(aliases=["hush", "shush", "stfu", "silence"])
    async def shutup(self, ctx: commands.Context):
        """Makes the bot stop announcing every song
        Preferably use `nowplaying` to see what the bot is singing"""
        async with self.bot.pool.acquire() as conn:
            is_silent = await conn.fetchone(
                "SELECT value FROM guildConfig WHERE id = ? AND key = 'silent';",
                (ctx.guild.id),
            )

            if is_silent:
                await conn.execute("DELETE FROM guildConfig WHERE key = 'silent';")
            else:
                await conn.execute(
                    "INSERT INTO guildConfig (id, key, value) VALUES (:id, 'silent', :value);",
                    {"id": ctx.guild.id, "value": True},
                )

            await conn.commit()

        if not is_silent:
            await ctx.message.add_reaction("\N{FACE WITH FINGER COVERING CLOSED LIPS}")
        else:
            await ctx.message.add_reaction(
                "\N{SPEAKING HEAD IN SILHOUETTE}\N{VARIATION SELECTOR-16}"
            )


async def setup(bot: "AceBot"):
    await bot.add_cog(Music(bot))
