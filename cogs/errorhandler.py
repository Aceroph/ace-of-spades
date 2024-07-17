import difflib
import traceback
from typing import TYPE_CHECKING, Union

import discord
import wavelink
from discord.ext import commands

from utils import dynamic, errors, misc, paginator, subclasses
from utils.errors import iserror

if TYPE_CHECKING:
    from main import AceBot


# Reinvocation
async def reinvoke(ctx: commands.Context):
    command = ctx.message.content.split()[0].strip(ctx.prefix)

    # Get closest match for command
    correct_command: Union[commands.Command, commands.Group] = None
    ratio: float = 0.5
    cmd: commands.Command
    for cmd in ctx.bot.commands:
        try:
            await cmd.can_run(ctx)
            r = difflib.SequenceMatcher(None, command, cmd.qualified_name).ratio()
            if r > ratio:
                correct_command = cmd
                ratio = r
        except:
            pass

    if not correct_command:
        return

    # Is commands a group?
    if hasattr(correct_command, "commands"):
        command = ctx.message.content.split()
        command = (
            " ".join(command[:2]).strip(ctx.prefix)
            if len(command) > 1
            else command[0].strip(ctx.prefix)
        )
        ratio: float = 0.75
        for cmd in correct_command.commands:
            r = difflib.SequenceMatcher(None, command, cmd.qualified_name).ratio()
            if r > ratio:
                correct_command = cmd
                ratio = r

    # Invoke command
    async def invoke(interaction: discord.Interaction):
        args = ctx.message.content.split()[
            len(correct_command.qualified_name.split()) :
        ]
        if interaction.guild:
            await interaction.message.delete()
        else:
            await interaction.response.edit_message(
                content="Reinvoked command successfully !", view=None
            )

        # If command is help
        if correct_command.qualified_name == "help":
            if len(args) >= 1:
                await ctx.send_help(" ".join(args))
            else:
                await ctx.send_help()
        else:
            r = [
                await commands.run_converters(ctx, param.converter, args[i], param)
                for i, param in enumerate(correct_command.params.values())
                if i < len(args)
            ]
            try:
                await correct_command.call_before_hooks(ctx)
                return await ctx.invoke(correct_command, *r)
            except Exception as err:
                return await on_command_error(ctx, err)

    # UI
    _invoke = discord.ui.Button(style=discord.ButtonStyle.green, label="Yes")
    _invoke.callback = invoke

    view = subclasses.View()
    view.add_item(_invoke)
    view.add_item(dynamic.QuitButton(author=ctx.author, guild=ctx.guild, label="Nah"))

    return await ctx.reply(
        f"Did you mean: `{correct_command.qualified_name}`",
        mention_author=False,
        view=view,
    )


# Error handler
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    # Defer if interaction
    if ctx.interaction and not ctx.interaction.response.is_done():
        await ctx.interaction.response.defer()

    if iserror(error, commands.errors.CommandNotFound):
        return await reinvoke(ctx)

    if iserror(error, commands.errors.MissingPermissions):
        return await ctx.reply(
            embed=discord.Embed(
                title=":warning: Missing permissions",
                description=f"> `{'` `'.join(error.missing_permissions)}`",
            ),
            mention_author=False,
            delete_after=15,
        )

    if iserror(error, commands.errors.MissingRequiredArgument):
        correction = f"{ctx.command} {ctx.command.signature}"
        missing_arg = error.args[0].split()[0]
        return await ctx.reply(
            embed=discord.Embed(
                title=":warning: Missing required argument",
                description=f">>> ```\n{correction}\n{' '*(len(correction)-(len(missing_arg)+1)) + '^'*len(missing_arg)}```",
            ),
            mention_author=False,
            delete_after=15,
        )

    if iserror(error, commands.errors.NoPrivateMessage):
        return await ctx.reply(
            embed=discord.Embed(
                title=":warning: Guild-only command",
                description="> This command cannot be used in DMs",
            ),
            mention_author=False,
            delete_after=15,
        )

    if iserror(error, errors.NotVoiceMember):
        return await ctx.reply(
            embed=discord.Embed(
                title=":warning: Cannot use command",
                description=f"> You are not connected to {error.channel.mention}",
            ),
            mention_author=False,
            delete_after=15,
        )

    if iserror(error, (commands.errors.CheckFailure, commands.errors.NotOwner)):
        return

    if iserror(error, errors.NoVoiceFound):
        return await ctx.reply(
            embed=discord.Embed(
                title=":musical_note: No Voice Found",
                description=f"> Please join a voice channel first before using this command.",
            ),
            mention_author=False,
            delete_after=15,
        )

    if iserror(error, errors.PlayerConnectionFailure):
        return await ctx.reply(
            embed=discord.Embed(
                title=":musical_note: Player Connection Failure",
                description=f"> I was unable to join this voice channel. Please try again.",
            ),
            mention_author=False,
            delete_after=15,
        )

    if iserror(error, commands.errors.CommandInvokeError):
        if isinstance(error.original, wavelink.LavalinkLoadException):
            embed = discord.Embed(
                title=":musical_note: Failed to load track",
                description=f">>> {error.original.error}",
            )
            return await ctx.reply(embed=embed, delete_after=15, mention_author=False)

    if iserror(error, errors.ModuleDisabled):
        return await ctx.reply(
            embed=discord.Embed(
                title=":warning: Command unavailable",
                description=f"> The module `{error.module}` is disabled in this server",
            ),
            mention_author=False,
            delete_after=15,
        )

    # UNHANDLED ERRORS BELLOW
    # Process the traceback to clean path !
    try:
        await ctx.message.add_reaction(misc.dislike)
    except:
        pass
    trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))

    command_used = (
        "```\n" + ctx.message.content.replace("`", "'") + "```"
        if ctx.message.content
        else f"{misc.curve} </{ctx.interaction.command.qualified_name}:{int(ctx.interaction.data['id'])}>"
        or None
    )

    embed = discord.Embed(
        title=f":warning: Unhandled error in command",
        description=f"By: `{ctx.author.display_name}` (ID: {ctx.author.id})\nIn: `{ctx.guild.name if ctx.guild else 'DMs'}` {f'(ID: {ctx.guild.id})' if ctx.guild else ''}",
    )
    embed.add_field(name="Command", value=command_used, inline=False)

    # Paginate if too long
    prefix = f"```py\n"
    if len(prefix + trace) > 1024:
        p = paginator.Paginator(
            ctx, embed=embed, prefix=prefix, suffix="```", subtitle="Traceback"
        )
        for line in misc.clean_traceback(trace).split("\n"):
            p.add_line(line)

        # Send full traceback to owner
        await p.start(destination=ctx.bot.get_user(ctx.bot.owner_id))
    else:
        embed.add_field(name="Traceback", value=prefix + trace + "```")
        await ctx.bot.get_user(ctx.bot.owner_id).send(embed=embed)

    # User error
    embed = discord.Embed(
        title=f":warning: {type(error).__qualname__}",
        description=f"> {' '.join(error.args)}" if len(error.args) > 0 else None,
    )
    return await ctx.reply(embed=embed, mention_author=False, delete_after=15)


async def setup(bot: "AceBot"):
    bot.add_listener(on_command_error)
