import textwrap
from typing import TYPE_CHECKING, List

import discord
from discord import app_commands
from discord.ext import commands

from utils import errors, misc, subclasses
from utils.dynamic import QuitButton

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


class HelpView(subclasses.View):
    def __init__(self, bot: "AceBot", ctx: commands.Context):
        super().__init__()
        self.bot = bot
        self.ctx = ctx

    def welcome_page(self) -> discord.Embed:
        # METHOD.chain().chain().chain()...
        embed = ( 
            discord.Embed(
                color=discord.Color.blurple(),
                title="Help Page",
                description=f"> Use `{self.ctx.prefix}help command/group` for more info on a command",
            ) # Syntax        
            .add_field(     
                name="Command Syntax",
                value=(
                    f">>> My prefixes are `{self.ctx.prefix}` and {self.bot.user.mention}\n"
                    "My commands and prefix are case-insensitive\n"
                    "I also auto-correct mistakes"
                ),
                inline=False,
            )
            .add_field(
                name="Arguments",
                value=f">>> `<arg>` -> This argument is required\n`[arg]` -> This argument is optional",
                inline=False,
            )   # Side note
            .set_footer(text="Do not type in the brackets or any ponctuation !")
        )
        return embed

    async def commands_page(self) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.blurple())

        # Modules & Commands
        for name, module in self.bot.cogs.items():
            # Filter commands
            filtered_commands = await filter_commands(self.ctx, module.walk_commands())
            if len(filtered_commands) == 0:
                continue

            filtered_commands.sort(key=lambda c: c.qualified_name)

            MAX = 4

            columns = [
                filtered_commands[i : i + MAX]
                for i in range(0, len(filtered_commands), MAX)
            ]

            embed.add_field(
                name=f"{module.emoji}  {name} - {len(filtered_commands)}",
                value="```ansi\n"
                + "\n".join(
                    [
                        "".join(
                            [
                                ("\u001b[0;34m" + column[i].qualified_name).ljust(
                                    max([len(cmd.qualified_name) for cmd in column])
                                    + 12
                                )
                                for column in columns
                                if i < len(column)
                            ]
                        )
                        for i in range(MAX)
                    ]
                )
                + "```",
                inline=False,
            )

        return embed

    @discord.ui.button(
        label="Show commands",
        emoji="<:info:1221344535754313758>",
        style=discord.ButtonStyle.blurple,
    )
    async def change_page(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        if interaction.user != self.ctx.author:
            raise errors.NotYourButton

        match self.change_page.label:
            case "Show commands":
                self.change_page.label = "Back to help"
                return await interaction.response.edit_message(
                    embed=await self.commands_page(), view=self
                )

            case "Back to help":
                self.change_page.label = "Show commands"
                return await interaction.response.edit_message(
                    embed=self.welcome_page(), view=self
                )


class HelpCog(subclasses.Cog):
    def __init__(self, bot: commands.Bot | None = None, emoji: str | None = None):
        super().__init__(bot, emoji)

    @commands.hybrid_command(name="help", aliases=["h"], hidden=True)
    @app_commands.describe(entity="The command you need help with")
    async def _help(self, ctx: commands.Context, *, entity: str = None):
        """Perhaps you do not know how to use this bot?"""
        view = HelpView(self.bot, ctx)

        if not entity:
            view.add_item(QuitButton(author=ctx.author, guild=ctx.guild))
            return await ctx.reply(
                embed=view.welcome_page(), view=view, mention_author=False
            )

        command = self.bot.get_command(entity)
        if not command:
            return await ctx.reply(
                f"No command called {entity}", delete_after=5, mention_author=False
            )

        """if command not in await filter_commands(
            ctx, self.bot.walk_commands(), show_hidden=True
        ):
            raise commands.CheckFailure"""

        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f"{misc.info} {command.qualified_name} {command.signature}",
        )
        embed.set_author(
            name=f"{ctx.author.display_name} : Help -> {command.cog.qualified_name}",
            icon_url=ctx.author.avatar.url,
        )

        ## Documentation
        failure = "Failed to fetch documentation\nProbably forgot to write one for this command\nThis is awkward.."
        embed.add_field(
            name="Documentation",
            value=f">>> {'\n'.join(textwrap.wrap(command.help, width=len(command.help.splitlines()[0]))) if command.help else failure}",
            inline=False,
        )

        ## App command version
        if isinstance(command, commands.HybridCommand):
            app_cmds: list[app_commands.AppCommand] = (
                await self.bot.tree.fetch_commands()
            )
            for cmd in app_cmds:
                if cmd.name == command.qualified_name:
                    embed.add_field(
                        name="App command", value=f"{misc.curve} {cmd.mention}"
                    )

        ## Authorization
        mentions = [ctx.author.mention if not ctx.guild else "@everyone"]

        data = {
            "user": {
                "name": None,
                "username": None,
                "id": 0,
                "discriminator": None,
                "avatar": None,
            },
            "roles": [],
            "flags": 0,
        }
        dummy = discord.Member(data=data, guild=ctx.guild, state=ctx.author._state)
        dummy_context = commands.Context(
            message=ctx.message, bot=self.bot, view=ctx.view
        )
        dummy_context.author = dummy

        try:
            await command.can_run(dummy_context)
        except Exception as err:
            if isinstance(err, commands.NotOwner):
                mentions = [f"<@{self.bot.owner_id}>"]

            elif isinstance(err, commands.NoPrivateMessage):
                mentions = ["Guild only"]

            elif isinstance(err, commands.MissingPermissions):
                mentions = [perm.capitalize() for perm in err.missing_permissions]

            elif isinstance(err, commands.MissingRole):
                mentions = [f"<@&{err.missing_role}>"]

            else:
                mentions = ["Unknown requirement"]

        embed.add_field(
            name="Authorizations",
            value=misc.curve + f"\n{misc.space}".join(mentions),
        )

        ## Aliases if any
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

        return await ctx.reply(
            embed=embed,
            mention_author=False,
        )

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
    await bot.add_cog(HelpCog(bot=bot))
