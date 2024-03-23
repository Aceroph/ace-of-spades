from typing import Union, TYPE_CHECKING
from utils import subclasses, misc
from discord.ext import commands
import textwrap
import discord

if TYPE_CHECKING:
    from main import AceBot


class AceHelp(commands.HelpCommand):
    old: discord.Embed = None
    old_view: subclasses.View = None

    async def show_info(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.old, view=self.old_view)

    async def show_commands(self, interaction: discord.Interaction):
        if self.context.author == interaction.user:
            self.old = interaction.message.embeds[0]
            embed = discord.Embed(color=discord.Color.blurple())
            embed.set_thumbnail(url=misc.docs)
            embed.set_author(
                name=f"{self.context.author.display_name}: Help",
                icon_url=self.context.author.avatar.url,
            )

            # Modules & Commands
            for name, module in self.context.bot.cogs.items():
                # Filter commands
                filtered_commands = await self.filter_commands(module.get_commands())
                cmds = [f"`{command.qualified_name}`" for command in filtered_commands]
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
            info.callback = self.show_info
            view.add_item(info)
            view.add_quit(interaction.user, interaction.guild)
            return await interaction.response.edit_message(embed=embed, view=view)
        else:
            return await interaction.response.send_message(
                "This is not your instance !", ephemeral=True
            )

    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            color=discord.Color.blurple(),
            title="Help Page",
            description=f"> Use `b.help command/group` for more info on a command",
        )
        embed.set_thumbnail(url=misc.docs)
        embed.set_author(
            name=f"{self.context.author.display_name} : Help",
            icon_url=self.context.author.avatar.url,
        )

        # Syntax
        embed.add_field(
            name="Command Syntax",
            value=f">>> My prefix is `{self.context.prefix}`\nMy commands and prefix are case-insensitive\nI will try me best to correct you if you don knoe how ti spel :grin:",
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
        info.callback = self.show_commands
        view.add_item(info)
        self.old_view = view.add_quit(self.context.author, self.context.guild)

        await self.context.reply(embed=embed, view=view)

    async def send_command_help(self, command: Union[commands.Command, commands.Group]):
        if command not in await self.filter_commands(self.context.bot.walk_commands()):
            raise commands.CheckFailure

        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f"{misc.tilde} {self.context.prefix}{command.qualified_name} {command.signature}",
        )
        embed.set_thumbnail(url=misc.docs)
        embed.set_author(
            name=f"{self.context.author.display_name} : Help -> {command.cog.qualified_name}",
            icon_url=self.context.author.avatar.url,
        )

        # Documentation
        failure = "Failed to fetch documentation\nProbably forgot to write one for this command\nThis is awkward.."
        embed.add_field(
            name="Documentation",
            value=f">>> {command.help.format(curve=misc.curve) if command.help else failure}",
            inline=False,
        )

        # Subcommands if group
        if isinstance(command, commands.Group):
            subs = "\n".join(
                textwrap.wrap(
                    text=" ".join(
                        [f"`{command.name}`" for command in command.commands]
                    ),
                    width=len(misc.curve) + 35,
                    initial_indent=misc.curve,
                    subsequent_indent=misc.space,
                )
            )
            embed.add_field(
                name=f"Sub commands",
                value=subs,
                inline=True,
            )

        # Aliases if any
        if command.aliases != []:
            embed.add_field(
                name=f"Aliases",
                value=f"{misc.curve} `{'` `'.join(command.aliases)}`",
                inline=True,
            )

        return await self.context.reply(
            embed=embed,
            view=subclasses.View().add_quit(self.context.author, self.context.guild),
        )

    async def send_group_help(self, group: commands.Group):
        return await self.send_command_help(group)

    async def send_error_message(self, error):
        await self.context.reply(error)


async def setup(bot: "AceBot"):
    bot.help_command = AceHelp()
