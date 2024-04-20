from utils import subclasses, misc, paginator, errors, context
from typing import TYPE_CHECKING, Union
from discord.ext import commands
from utils.errors import iserror
import traceback
import wavelink
import discord
import difflib

if TYPE_CHECKING:
    from main import AceBot


# Error handler
async def on_command_error(ctx: context.Context, error: commands.CommandError):
    # Defer if interaction
    if ctx.interaction and not ctx.interaction.response.is_done():
        await ctx.interaction.response.defer()

    if iserror(error, commands.errors.CommandNotFound):
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
                await correct_command.call_before_hooks(ctx)
                await ctx.invoke(correct_command, *r)

        # UI
        _invoke = discord.ui.Button(style=discord.ButtonStyle.green, label="Yes")
        _invoke.callback = invoke

        view = subclasses.View()
        view.add_item(_invoke)
        view.add_quit(ctx.author, ctx.guild, label="Nah")

        return await ctx.reply(
            f"Did you mean: `{correct_command.qualified_name}`",
            mention_author=False,
            view=view,
        )

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
        startPos = correction.find(missing_arg)
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

    # UNHANDLED ERRORS BELLOW
    # Process the traceback to clean path !
    try:
        await ctx.message.add_reaction(misc.dislike)
    except:
        pass
    trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    description = f"Command:\n```\n{ctx.message.content or 'None'}```\nTraceback:\n```py\n{misc.clean_traceback(trace)}```"

    embed = discord.Embed(
        title=f":warning: Unhandled error in command",
        description=f"Command:\n```\n{ctx.message.content or 'None'}```",
    )
    embed.set_footer(
        text=f"Caused by {ctx.author.display_name} in {ctx.guild.name if ctx.guild else 'DMs'} ({ctx.guild.id if ctx.guild else 0})",
        icon_url=ctx.author.avatar.url,
    )

    # Paginate if too long
    if len(description) > 4080:
        p = paginator.Paginator(
            ctx,
            embed=embed,
            prefix=f"Traceback:\n```py",
            suffix="```",
        )
        for line in misc.clean_traceback(trace).split("\n"):
            p.add_line(line)

        # Send full traceback to owner
        await p.start(destination=ctx.bot.get_user(ctx.bot.owner_id))
    else:
        embed.description = description
        await ctx.bot.get_user(ctx.bot.owner_id).send(embed=embed)

    view = subclasses.View()
    view.add_quit(ctx.author, ctx.guild)

    # User error
    embed = discord.Embed(
        title=f":warning: {type(error).__qualname__}",
        description=f"> {' '.join(error.args)}" if len(error.args) > 0 else None,
    )
    return await ctx.reply(
        embed=embed, view=view, mention_author=False, delete_after=15
    )


async def setup(bot: "AceBot"):
    bot.add_listener(on_command_error)
