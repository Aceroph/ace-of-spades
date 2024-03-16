from typing import TYPE_CHECKING, cast
from utils import subclasses, misc
from discord.ext import commands
from tabulate import tabulate
import wavelink
import textwrap
import discord

if TYPE_CHECKING:
    from main import AceBot


class Music(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.bot = bot
        self.emoji = '\N{MUSICAL NOTE}'
    

    async def cog_load(self):
        nodes = [wavelink.Node(uri="http://lavalink.jirayu.pw:2333", password="youshallnotpass")]
        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)
    

    @subclasses.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        self.bot.logger.info(f"Wavelink node connected: {payload.node!r} | Resumed: {payload.resumed}")
    

    @subclasses.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player: wavelink.Player | None = payload.player
        if not player:
            return

        track: wavelink.Playable = payload.track
        length = f"{track.length//60000}:{format(track.length//1000 % 60, '02d')}"
        current_time = f"{player.position//60000}:{format(player.position//1000 % 60, '02d')}"
        fraction = int(player.position/track.length * 15)

        embed: discord.Embed = discord.Embed(title="Now Playing", description=f"{track.title}\n{misc.curve}by `{track.author}`\n\n```\n{current_time} [{fraction * '='}{(15 - fraction) * '-'}] {length}```", color=discord.Color.blurple())

        if track.recommended:
            embed.set_footer(text=f"Recommended by {track.source}")
        else:
            embed.set_footer(text=f"Requested by {track.extras.name}", icon_url=track.extras.icon_url or None)

        await player.home.send(embed=embed)

    
    @commands.command(aliases=['np', 'now'])
    async def nowplaying(self, ctx: commands.Context) -> None:
        player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        track: wavelink.Playable = player.current
        length = f"{track.length//60000}:{format(track.length//1000 % 60, '02d')}"
        current_time = f"{player.position//60000}:{format(player.position//1000 % 60, '02d')}"
        fraction = int(player.position/track.length * 15)

        embed: discord.Embed = discord.Embed(title="Now Playing", description=f"{track.title}\n{misc.curve}by `{track.author}`\n\n```\n{current_time} [{fraction * '='}{(15 - fraction) * '-'}] {length}```", color=discord.Color.blurple())

        if track.recommended:
            embed.set_footer(text=f"Recommended by {track.source}")
        else:
            embed.set_footer(text=f"Requested by {track.extras.name or None}", icon_url=track.extras.icon_url or None)

        await player.home.send(embed=embed)


    @commands.command(aliases=['p'])
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a song with the given query."""
        if not ctx.guild:
            return

        player: wavelink.Player
        player = cast(wavelink.Player, ctx.voice_client)  # type: ignore

        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)  # type: ignore
            except AttributeError:
                await ctx.send("Please join a voice channel first before using this command.")
                return
            except discord.ClientException:
                await ctx.send("I was unable to join this voice channel. Please try again.")
                return

        # Turn on AutoPlay to enabled mode.
        # enabled = AutoPlay will play songs for us and fetch recommendations...
        # partial = AutoPlay will play songs for us, but WILL NOT fetch recommendations...
        # disabled = AutoPlay will do nothing...
        player.autoplay = wavelink.AutoPlayMode.enabled

        # Lock the player to this channel...
        if not hasattr(player, "home"):
            player.home = ctx.channel
        elif player.home != ctx.channel:
            await ctx.send(f"You can only play songs in {player.home.mention}, as the player has already started there.")
            return

        # This will handle fetching Tracks and Playlists...
        # Seed the doc strings for more information on this method...
        # If spotify is enabled via LavaSrc, this will automatically fetch Spotify tracks if you pass a URL...
        # Defaults to YouTube for non URL based queries...
        tracks: wavelink.Search = await wavelink.Playable.search(query)
        if not tracks:
            await ctx.send(f"{ctx.author.mention} - Could not find any tracks with that query. Please try again.")
            return

        if isinstance(tracks, wavelink.Playlist):
            # Add requested user to tracks
            for track in tracks.tracks:
                track.extras = {'name': ctx.author.display_name, 'icon_url': ctx.author.display_avatar.url}

            added: int = await player.queue.put_wait(tracks)

            length = sum([t.length//1000 for t in tracks.tracks])
            length_fmt = f"{length//3600}h{format(length//60 % 60, '02d')}m{format(length % 60, '02d')}s"
            
            embed = discord.Embed(title="Added playlist to queue", description=f"loaded `{added}` songs from `{tracks.name}`\n{misc.curve}total length: {length_fmt}")
            await ctx.reply(embed=embed, mention_author=False)

        else:
            # Add requested user to track
            track: wavelink.Playable = tracks[0]
            track.extras = {'name': ctx.author.display_name, 'icon_url': ctx.author.display_avatar.url}

            await player.queue.put_wait(track)
            embed = discord.Embed(title="Added song to queue", description=f"{track.title}\n{misc.curve}by `{track.author}`")
            await ctx.reply(embed=embed, mention_author=False)

        if not player.playing:
            # Play now since we aren't playing anything...
            await player.play(player.queue.get(), volume=30)
    

    @commands.command()
    @commands.guild_only()
    async def queue(self, ctx: commands.Context):
        """Lists the next titles and position in the queue"""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.reply("Player is not connected !", mention_author=False)
    
        length = len(player.queue._items)
        if length > 0:
            paginator = subclasses.Paginator(ctx=ctx, embed=discord.Embed(title=f'Queue ({str(length) + ' songs' if length > 1 else str(length) + ' song'})', color=discord.Color.blurple()), max_lines=20, prefix="```", suffix="```")
            items = [[format(i+1, '02d'), textwrap.shorten(track.title, 45, break_long_words=False, placeholder='...')] for i, track in enumerate(player.queue._items)]
            pages = [items[p:p+20] for p in range(0, len(items), 20)]

            for page in pages:
                table = tabulate(headers=['No#', 'Track'], tabular_data=page, tablefmt='outline', stralign='left', numalign='left')
                paginator.add_page(table)

            await paginator.start()
        else:
            await ctx.reply('Queue empty !', mention_author=False)
    

    @commands.command()
    @commands.guild_only()
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the current player's queue"""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

        length = len(player.queue._items)
        if length > 1:
            player.queue.shuffle()
            embed = discord.Embed(title="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS} Shuffled queue", description=f">>> reordered {length} items", color=discord.Color.blurple())
        else:
            embed = discord.Embed(title="\N{CROSS MARK} Did not shuffle queue", description=f"> why shuffle {length + ' item' if length > 0 else 'nothing'}?")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    
    @commands.command()
    @commands.guild_only()
    async def pause(self, ctx: commands.Context):
        """Pauses or resumes activity"""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

        await player.pause(not player.paused)
        if not player.paused:
            embed = discord.Embed(title="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16} Resumed player", description=f"{misc.curve} to pause, run the command again", color=discord.Color.blurple())
        else:
            embed = discord.Embed(title="\N{DOUBLE VERTICAL BAR}\N{VARIATION SELECTOR-16} Paused player", description=f"{misc.curve} to resume, run the command again", color=discord.Color.blurple())

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(aliases=['next'])
    @commands.guild_only()
    async def skip(self, ctx: commands.Context):
        """Skips the current song"""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        
        await player.skip()
        await ctx.reply('Skipped song', mention_author=False)
    

    @commands.command(aliases=['quit'])
    @commands.guild_only()
    async def stop(self, ctx: commands.Context):
        """Stops playing music and disconnects the player"""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

        await player.disconnect()
        await ctx.reply('Stopped playing music', mention_author=False)


async def setup(bot: 'AceBot'):
    await bot.add_cog(Music(bot))