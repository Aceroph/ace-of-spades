import textwrap
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils import misc, subclasses

if TYPE_CHECKING:
    from main import AceBot


async def filter_commands(
    ctx: commands.Context, commands: list[commands.Command], show_hidden: bool = False
) -> list[commands.Command]:
    filtered_commands = []
    for cmd in commands:
        try:
            if await cmd.can_run(ctx) and (not cmd.hidden or show_hidden):
                filtered_commands.append(cmd)
        except:
            pass
    return filtered_commands


class Help(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        self.bot = bot

    @commands.hybrid_command(name="help", aliases=["h"], hidden=True)
    @app_commands.describe(entity="The command you need help with")
    async def _help(self, ctx: commands.Context, entity: str = None):
        """Perhaps you do not know how to use this bot?"""
        ctx.old = None
        ctx.old_view = None

        if entity:
            command = self.bot.get_command(entity)
            if not command:
                return await ctx.send(f"No command called {entity}")

            if command not in await filter_commands(
                ctx, self.bot.walk_commands(), show_hidden=True
            ):
                raise commands.CheckFailure

            embed = discord.Embed(
                color=discord.Color.blurple(),
                title=f"{misc.info} {command.qualified_name} {command.signature}",
            )
            embed.set_author(
                name=f"{ctx.author.display_name} : Help -> {command.cog.qualified_name}",
                icon_url=ctx.author.avatar.url,
            )

            # Documentation
            failure = "Failed to fetch documentation\nProbably forgot to write one for this command\nThis is awkward.."
            embed.add_field(
                name="Documentation",
                value=f">>> {command.help.format(curve=misc.curve) if command.help else failure}",
                inline=False,
            )

            # Authorization if any
            mentions = [ctx.author.mention if not ctx.guild else "@everyone"]
            if isinstance(command, commands.HybridCommand):
                app_cmds: list[app_commands.AppCommand] = (
                    await self.bot.tree.fetch_commands()
                )
                for cmd in app_cmds:
                    if cmd.name == command.qualified_name:
                        embed.add_field(
                            name="App command", value=f"{misc.curve} {cmd.mention}"
                        )
                        if ctx.guild:
                            try:
                                perms = await cmd.fetch_permissions(ctx.guild)
                                mentions = [p.target.mention for p in perms.permissions]
                                break
                            except discord.NotFound:
                                break

            embed.add_field(
                name="Authorizations",
                value=misc.curve + f"\n{misc.space}".join(mentions),
            )

            # Subcommands if group
            if isinstance(command, commands.Group):
                embed.add_field(
                    name=f"Subcommands",
                    value=f"{misc.curve}`"
                    + f"`\n{misc.space}`".join(
                        sorted(
                            [f"`{command.name}`" for command in command.commands],
                            key=lambda a: len(a),
                            reverse=True,
                        )
                    )
                    + "`",
                    inline=True,
                )

            # Aliases if any
            if command.aliases != []:
                embed.add_field(
                    name=f"Aliases",
                    value=f"{misc.curve}`"
                    + f"`\n{misc.space}`".join(
                        sorted(command.aliases, key=lambda a: len(a), reverse=True)
                    )
                    + "`",
                    inline=True,
                )

            return await ctx.send(
                embed=embed, view=subclasses.View().add_quit(ctx.author, ctx.guild)
            )

        async def show_info(interaction: discord.Interaction):
            await interaction.response.edit_message(embed=ctx.old, view=ctx.old_view)

        async def show_commands(interaction: discord.Interaction):
            if ctx.author == interaction.user:
                ctx.old = interaction.message.embeds[0]
                embed = discord.Embed(color=discord.Color.blurple())
                embed.set_author(
                    name=f"{ctx.author.display_name}: Help",
                    icon_url=ctx.author.avatar.url,
                )

                # Modules & Commands
                for name, module in self.bot.cogs.items():
                    # Filter commands
                    filtered_commands = await filter_commands(
                        ctx, module.get_commands()
                    )

                    cmds = [
                        f"`{command.qualified_name}`" for command in filtered_commands
                    ]
                    (
                        embed.add_field(
                            name=f"{module.emoji} {name} - {len(cmds)}",
                            value="\n".join(
                                textwrap.wrap(
                                    " | ".join(cmds),
                                    width=70,
                                    initial_indent=f"{misc.space}",
                                    subsequent_indent=f"{misc.space}",
                                    break_long_words=False,
                                )
                            ),
                            inline=False,
                        )
                        if len(cmds) > 0
                        else None
                    )

                view = subclasses.View()
                info = discord.ui.Button(
                    label="Back to help", emoji="\N{INFORMATION SOURCE}"
                )
                info.callback = show_info
                view.add_item(info)
                view.add_quit(interaction.user, interaction.guild)
                return await interaction.response.edit_message(embed=embed, view=view)
            else:
                return await interaction.response.send_message(
                    "This is not your instance !", ephemeral=True
                )

        if not entity:
            prefixes = self.bot.command_prefix(self.bot, ctx.message)
            embed = discord.Embed(
                color=discord.Color.blurple(),
                title="Help Page",
                description=f"> Use `{prefixes[0]}help command/group` for more info on a command",
            )
            embed.set_author(
                name=f"{ctx.author.display_name} : Help",
                icon_url=ctx.author.avatar.url,
            )

            # Syntax
            embed.add_field(
                name="Command Syntax",
                value=f">>> My prefixes are `{prefixes[0]}` and {self.bot.user.mention}\nMy commands and prefix are case-insensitive\nI also auto-correct mistakes",
                inline=False,
            )
            embed.add_field(
                name="Arguments",
                value=f">>> `<arg>` -> This argument is required\n`[arg]` -> This argument is optional",
                inline=False,
            )

            # Side note
            embed.set_footer(text="Do not type in the brackets or any ponctuation !")

            # View
            view = subclasses.View()
            info = discord.ui.Button(
                label="Show commands",
                style=discord.ButtonStyle.grey,
                emoji="\N{INFORMATION SOURCE}",
            )
            info.callback = show_commands
            view.add_item(info)
            ctx.old_view = view.add_quit(ctx.author, ctx.guild)

            await ctx.send(embed=embed, view=view)

    @_help.autocomplete("entity")
    async def help_autocomplete(self, interaction: discord.Interaction, current: str):
        return sorted(
            [
                app_commands.Choice(
                    name=c.qualified_name.capitalize(), value=c.qualified_name
                )
                for c in self.bot.walk_commands()
                if current.casefold() in c.qualified_name or len(current) == 0
            ],
            key=lambda c: c.name,
        )[:25]


async def setup(bot: "AceBot"):
    await bot.add_cog(Help(bot))
