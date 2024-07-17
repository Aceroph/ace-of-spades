import time
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

import discord
from discord import Message, app_commands
from discord.ext import commands

from . import errors, misc, paginator
from .dynamic import QuitButton

if TYPE_CHECKING:
    from main import AceBot


async def reply(
    ctx: commands.Context,
    content: str,
    prefix: str = "",
    suffix: str = "",
    *args,
    **kwargs,
) -> Message:
    if ctx.interaction and ctx.interaction.response.is_done():
        if len(prefix + content + suffix) > 2000:
            p = paginator.Paginator(ctx, prefix=prefix, suffix=suffix, max_lines=100)
            for line in content.split("\n"):
                p.add_line(line)
            return await p.start()

        return await ctx.interaction.followup.send(
            prefix + content + suffix, *args, **kwargs
        )
    else:
        if len(prefix + content + suffix) > 2000:
            p = paginator.Paginator(ctx, prefix=prefix, suffix=suffix, max_lines=100)
            for line in content.split("\n"):
                p.add_line(line)
            return await p.start()

        return await ctx.reply(
            prefix + content + suffix, *args, **kwargs, mention_author=False
        )


async def can_use(ctx: commands.Context):
    if ctx.guild and isinstance(ctx.author, discord.Member):
        if isinstance(ctx.command, commands.HybridCommand):
            app_cmds: list[app_commands.AppCommand] = (
                await ctx.bot.tree.fetch_commands()
            )
            for cmd in app_cmds:
                if cmd.name == ctx.command.qualified_name:
                    try:
                        perms = await cmd.fetch_permissions(ctx.guild)
                        targets = [p.target for p in perms.permissions]
                        return any(
                            [
                                ctx.author in targets,
                                any([r in targets for r in ctx.author.roles]),
                                ctx.channel in targets,
                            ]
                        )
                    except discord.NotFound:
                        break
    return True


@dataclass
class Setting:
    annotation: Any
    default: Any = None


class Cog(commands.Cog):
    def __init__(self, bot: Optional[commands.Bot] = None, emoji: Optional[str] = None):
        self.bot: "AceBot" = bot
        self.emoji: str = emoji or "<:sadcowboy:1002608868360208565>"
        self.time: float = time.time()
        self.config: Dict[str, Setting] = {"disabled": Setting(bool, False)}

    async def get_setting(
        self, ctx: commands.Context, module: str, setting: str
    ) -> Optional[str]:
        assert ctx.guild is not None
        async with self.bot.pool.acquire() as conn:
            setting = await conn.fetchone(
                "SELECT value FROM guildConfig WHERE id = ? AND key LIKE '?:?';",
                (ctx.guild.id, module.casefold(), setting.upper()),
            )
            return setting[0] if setting else None

    async def cog_before_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            return await super().cog_before_invoke(ctx)

        try:
            if await commands.run_converters(
                ctx, bool, await self.get_setting(ctx, "disabled"), commands.Parameter
            ):
                raise errors.ModuleDisabled(self)
        except:
            pass

        if await can_use(ctx) or ctx.author.guild_permissions.administrator:
            return await super().cog_before_invoke(ctx)
        else:
            raise commands.errors.CheckFailure


class View(discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        if errors.iserror(error, errors.NotYourButton):
            return await interaction.response.send_message(
                error.reason or "This is not your button !", ephemeral=True
            )

        if errors.iserror(error, errors.NoVoiceFound):
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title=":musical_note: No Voice Found",
                    description=f"> Please join a voice channel first before using this command.",
                ),
                delete_after=15,
            )

        # UNHANDLED ERRORS BELLOW
        # Process the traceback to clean path !
        trace = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        embed = discord.Embed(
            title=f":warning: Unhandled error in item : {item.type}",
            description=f"```py\n{misc.clean_traceback(trace)}```",
        )
        embed.set_footer(
            text=f"Caused by {interaction.user.display_name} in {interaction.guild.name if interaction.guild else 'DMs'} ({interaction.guild.id if interaction.guild else 0})",
            icon_url=interaction.user.display_avatar.url,
        )

        view = View()

        # Owner embed w full traceback
        await interaction.client.get_user(interaction.client.owner_id).send(embed=embed)

        # User error
        embed = discord.Embed(
            title=f":warning: {type(error).__qualname__}",
            description=(f"> {' '.join(error.args)}" if len(error.args) > 0 else None),
        )

        # Stop fucking responding twice
        if interaction.response.is_done():
            return await interaction.followup.send(embed=embed, view=view)
        else:
            return await interaction.response.send_message(embed=embed, view=view)

    def add_quit(
        self,
        author: Optional[discord.User] = None,
        guild: Optional[discord.Guild] = None,
        label: str = "Close",
    ):
        if guild:
            return self.add_item(
                QuitButton(
                    author=getattr(author, "id", 0),
                    guild=guild.id,
                    label=label,
                )
            )

    async def stop(self) -> None:
        self.clear_items()
        super().stop()
