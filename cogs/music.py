from typing import TYPE_CHECKING, cast, Union, List
from utils import subclasses, misc, paginator
from discord.ext import commands
from discord import app_commands
from tabulate import tabulate
from cogs import errors
import traceback
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

    async def now_playing_logic(
        self, origin: Union[commands.Context, wavelink.TrackStartEventPayload]
    ):
        player = getattr(origin, "voice_client", getattr(origin, "player", None))

        # Formatting
        track: wavelink.Playable = (
            origin.original if hasattr(origin, "original") else player.current
        )

        length = f"{track.length//60000}:{format(track.length//1000 % 60, '02d')}"
        current_time = (
            f"{player.position//60000}:{format(player.position//1000 % 60, '02d')}"
        )
        fraction = int(player.position / track.length * 10)

        progress_bar = (
            f"\n\n{current_time} {fraction * misc.blueline}{(10 - fraction) * misc.whiteline} {length}"
            if isinstance(origin, commands.Context)
            else ""
        )
        embed = discord.Embed(
            title="Now Playing",
            description=f"\N{OPTICAL DISC} [`{track.title}`]({track.uri})\n{misc.curve} *by:* {track.author}"
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

        embed.set_image(url=track.artwork or track.album.url)

        if isinstance(origin, commands.Context):
            await origin.reply(embed=embed, mention_author=False)
        else:
            if hasattr(player, "home"):
                await player.home.send(embed=embed)

    async def cog_before_invoke(self, ctx: commands.Context) -> None:
        if ctx.voice_client and not hasattr(ctx.voice_client, "home"):
            ctx.voice_client.home = ctx.channel

        return await super().cog_before_invoke(ctx)

    async def isvoicemember(self, ctx: commands.Context) -> None:
        if ctx.voice_client:
            if (
                ctx.author.guild_permissions.administrator
                or ctx.author in ctx.voice_client.channel.members
            ):
                return await super().cog_before_invoke(ctx)
            else:
                raise errors.NotVoiceMember(channel=ctx.voice_client.channel)

    @subclasses.Cog.listener()
    async def on_wavelink_node_ready(
        self, payload: wavelink.NodeReadyEventPayload
    ) -> None:
        self.bot.logger.info(
            f"Wavelink node connected: {payload.node!r} | Resumed: {payload.resumed}"
        )

    @subclasses.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player) -> None:
        if hasattr(player, "home"):
            await player.home.send(
                f"The player has been inactive for `{player.inactive_timeout//60}` minutes."
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
    @commands.hybrid_command(aliases=["np", "now"])
    async def nowplaying(self, ctx: commands.Context) -> None:
        """Shows the current playing song"""
        if ctx.voice_client.current:
            return await self.now_playing_logic(ctx)
        else:
            return await ctx.reply(
                embed=discord.Embed(
                    title=":eyes: Nothing is playing",
                    description=f">>> Play something using `play`",
                ),
                mention_author=False,
                delete_after=15,
            )

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @commands.hybrid_command(aliases=["p"])
    @app_commands.describe(query="The song or link to search for")
    async def play(self, ctx: commands.Context, *, query: str = None) -> None:
        """Play a song with the given query."""
        player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)  # type: ignore
            except AttributeError:
                raise errors.NoVoiceFound
            except discord.ClientException:
                raise errors.PlayerConnectionFailure

        # Autoplay
        player.autoplay = wavelink.AutoPlayMode.enabled

        # If paused, play
        if player.paused and not query:
            return await ctx.invoke(self.bot.get_command("pause"))
        elif not query:
            raise commands.errors.MissingRequiredArgument(
                param=ctx.command.clean_params["query"]
            )

        if ctx.interaction:
            await ctx.interaction.response.defer()

        # If multiple songs are parsed
        if len(query.split(",")) > 1:
            tracks = []
            for q in query.split(",")[:5]:
                track = (await wavelink.Playable.search(q))[0]
                track.extras = {
                    "name": ctx.author.display_name,
                    "icon_url": ctx.author.display_avatar.url,
                }
                tracks.append(track)

            await player.queue.put_wait(tracks)
            length = misc.time_format(sum([t.length // 1000 for t in tracks]))
            embed = discord.Embed(
                title="\N{OPTICAL DISC} Added songs to queue",
                description="\n".join(
                    [
                        f"`{i+1:02d}` | [`{track.title}`]({track.uri}) *by:* `{track.author}`"
                        for i, track in enumerate(tracks)
                    ]
                ),
            )
            embed.set_footer(text="Total length: " + length)
            embed.set_author(
                name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
            )
            await ctx.reply(embed=embed, mention_author=False)
        else:
            tracks: wavelink.Search = await wavelink.Playable.search(query)

            if isinstance(tracks, wavelink.Playlist):
                # Add requested user to tracks
                for track in tracks.tracks:
                    track.extras = {
                        "name": ctx.author.display_name,
                        "icon_url": ctx.author.display_avatar.url,
                    }

                added: int = await player.queue.put_wait(tracks)

                length = misc.time_format(
                    sum([t.length // 1000 for t in tracks.tracks])
                )

                embed = discord.Embed(
                    title="Added playlist to queue",
                    description=f"\N{OPTICAL DISC} loaded `{added}` songs from [`{tracks.name}`]({query})\n{misc.curve} total length: {length}",
                )
                embed.set_author(
                    name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
                )
                await ctx.reply(embed=embed, mention_author=False)

            else:
                # Add requested user to track
                track: wavelink.Playable = tracks
                track.extras = {
                    "name": ctx.author.display_name,
                    "icon_url": ctx.author.display_avatar.url,
                }

                await player.queue.put_wait(track)
                embed = discord.Embed(
                    title="Added song to queue",
                    description=f"\N{OPTICAL DISC} [`{track.title}`]({track.uri})\n{misc.curve} by `{track.author}`",
                )
                embed.set_author(
                    name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
                )
                await ctx.reply(embed=embed, mention_author=False)

        if not tracks:
            print("error")
            await ctx.reply(
                f"{ctx.author.mention} - Could not find any tracks with that query. Please try again.",
                mention_author=False,
            )
            return

        if not player.playing:
            await player.play(player.queue.get(), volume=30)

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @commands.hybrid_group(aliases=["q"], fallback="show", invoke_without_command=True)
    async def queue(self, ctx: commands.Context):
        """Lists the next titles and position in the queue"""
        if not ctx.voice_client:
            raise errors.NoVoiceFound

        length = len(ctx.voice_client.queue._items)
        if length > 0:
            p = paginator.Paginator(
                ctx=ctx,
                embed=discord.Embed(
                    title=f"Queue ({str(length) + ' songs' if length > 1 else str(length) + ' song'})",
                    color=discord.Color.blurple(),
                ),
                max_lines=20,
            )
            items = [
                [
                    format(i + 1, "02d"),
                    textwrap.shorten(
                        track.title, 45, break_long_words=False, placeholder="..."
                    ),
                    track.uri,
                ]
                for i, track in enumerate(ctx.voice_client.queue._items)
            ]
            for item in items:
                p.add_line(f"`{item[0]}` | [`{item[1]}`]({item[2]})")

            await p.start()
        else:
            await ctx.reply("Queue empty !", mention_author=False)

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @queue.command(name="clear")
    async def queue_clear(self, ctx: commands.Context):
        """Clears the queue and stops the music"""
        if not ctx.voice_client:
            raise errors.NoVoiceFound

        ctx.voice_client.queue.clear()
        ctx.voice_client.autoplay = wavelink.AutoPlayMode.disabled
        await ctx.voice_client.skip()
        await ctx.reply("Cleared queue", mention_author=False)

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @commands.hybrid_command()
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the current player's queue"""
        if not ctx.voice_client:
            raise errors.NoVoiceFound

        length = len(ctx.voice_client.queue._items)
        if length > 1:
            ctx.voice_client.queue.shuffle()
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

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @commands.hybrid_command(aliases=["unpause"])
    async def pause(self, ctx: commands.Context):
        """Pauses or resumes activity"""
        if not ctx.voice_client:
            raise errors.NoVoiceFound

        await ctx.voice_client.pause(not ctx.voice_client.paused)
        if not ctx.voice_client.paused:
            embed = discord.Embed(
                title="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16} Resumed player",
                description=f"{misc.curve} to pause, run `pause`",
                color=discord.Color.blurple(),
            )
        else:
            embed = discord.Embed(
                title="\N{DOUBLE VERTICAL BAR}\N{VARIATION SELECTOR-16} Paused player",
                description=f"{misc.curve} to resume, run `play` or `unpause`",
                color=discord.Color.blurple(),
            )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @commands.hybrid_command(aliases=["next"])
    async def skip(self, ctx: commands.Context):
        """Skips the current song"""
        if not ctx.voice_client:
            raise errors.NoVoiceFound

        await ctx.voice_client.skip()
        await ctx.reply("Skipped song", mention_author=False)

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @commands.hybrid_command(aliases=["quit"])
    async def stop(self, ctx: commands.Context):
        """Stops playing music and disconnects the player"""
        if not ctx.voice_client:
            raise errors.NoVoiceFound

        await ctx.voice_client.disconnect()
        await ctx.reply("Stopped playing music", mention_author=False)

    @commands.guild_only()
    @commands.before_invoke(isvoicemember)
    @commands.hybrid_command(aliases=["hush", "shush", "stfu", "silence"])
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

        if not ctx.interaction:
            if not is_silent:
                await ctx.message.add_reaction(
                    "\N{FACE WITH FINGER COVERING CLOSED LIPS}"
                )
            else:
                await ctx.message.add_reaction(
                    "\N{SPEAKING HEAD IN SILHOUETTE}\N{VARIATION SELECTOR-16}"
                )
        else:
            if not is_silent:
                await ctx.reply("\N{FACE WITH FINGER COVERING CLOSED LIPS}")
            else:
                await ctx.reply(
                    "\N{SPEAKING HEAD IN SILHOUETTE}\N{VARIATION SELECTOR-16}"
                )


async def setup(bot: "AceBot"):
    await bot.add_cog(Music(bot))
