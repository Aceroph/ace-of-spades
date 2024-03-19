from utils import subclasses, misc
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING
import traceback
import discord
import difflib

if TYPE_CHECKING:
    from main import AceBot


class NotYourButton(app_commands.errors.AppCommandError):
    def __init__(self, reason: str=None) -> None:
        self.reason = reason


class PlayerConnectionFailure(commands.errors.CommandError):
    pass


class NoVoiceFound(commands.errors.CommandError):
    pass
    

# Error handler
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, (commands.errors.CheckFailure, commands.errors.NotOwner)):
        return
    
    if isinstance(error, commands.errors.CommandNotFound):
        # Find close matches
        command = ctx.message.content.split()[0].strip(ctx.prefix)

        # Check for commands the author can use
        available_cmds = []
        for cmd in ctx.bot.walk_commands():
            try:
                await cmd.can_run(ctx)
                available_cmds.append(cmd.qualified_name)
            except:
                pass

        results = [(difflib.SequenceMatcher(None, command, cmd), cmd) for cmd in available_cmds]
        top_results = sorted(results, reverse=True, key=lambda i : i[0].ratio())[:5]
        clean_results = []
        for r in top_results:
            if r[0].ratio() >= 0.40:
                _match = r[0].find_longest_match(0, len(command), 0, len(r[1]))
                longest_match = r[1][_match.b:_match.b + _match.size]
                clean_results.append(r[1].replace(longest_match, f"**__{longest_match}__**"))

        if len(clean_results) >= 1:
            cmds = '\n'.join(clean_results)
            embed = discord.Embed(title="Did you mean?", description=f">>> {cmds}", color=discord.Color.blurple())
            return await ctx.reply(embed=embed, delete_after=15, mention_author=False)
        return

    await ctx.message.add_reaction('\N{DOUBLE EXCLAMATION MARK}')
    
    if isinstance(error, commands.errors.MissingPermissions):
        return await ctx.reply(embed=discord.Embed(title=':warning: Missing permissions', description=f"> `{'` `'.join(error.missing_permissions)}`", color=discord.Color.red()))
    
    if isinstance(error, commands.errors.MissingRequiredArgument):
        return await ctx.reply(embed=discord.Embed(title=':warning: Missing Required Argument', description=f"> {' '.join(error.args)}", color=discord.Color.red()))
    
    if isinstance(error, commands.errors.NoPrivateMessage):
        return await ctx.reply(embed=discord.Embed(title=':warning: No Private Message', description=f'> This command cannot be used in DMs', color=discord.Color.red()))
    
    if isinstance(error, NoVoiceFound):
        return await ctx.reply(embed=discord.Embed(title=':warning: No Voice Found', description=f'> Please join a voice channel first before using this command.', color=discord.Color.red()))

    if isinstance(error, PlayerConnectionFailure):
        return await ctx.reply(embed=discord.Embed(title=':warning: Player Connection Failure', description=f'> I was unable to join this voice channel. Please try again.', color=discord.Color.red()))

    # UNHANDLED ERRORS BELLOW
    # Process the traceback to clean path !
    trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    embed = discord.Embed(title=f":warning: Unhandled error in command : {ctx.command if hasattr(ctx, 'command') else 'None'}", description=f"```py\n{misc.clean_traceback(trace)}```")
    embed.set_footer(text=f"Caused by {ctx.author.display_name} in {ctx.guild.name if ctx.guild else 'DMs'} ({ctx.guild.id if ctx.guild else 0})", icon_url=ctx.author.avatar.url)

    view = subclasses.View()
    view.add_quit(ctx.author)

    # Owner embed w full traceback
    await ctx.bot.get_user(ctx.bot.owner_id).send(embed=embed)

    # User error
    embed = discord.Embed(title=f":warning: {type(error).__qualname__}", description=f"> {' '.join(error.args)}" if len(error.args) > 0 else None)
    return await ctx.reply(embed=embed, view=view, mention_author=False)


async def setup(bot: 'AceBot'):
    bot.add_listener(on_command_error)