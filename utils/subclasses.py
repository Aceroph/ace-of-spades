from cogs.errors import NoVoiceFound, NotYourButton, iserror
from discord.ext import commands
from discord import app_commands
from . import subclasses, misc
import traceback
import discord
import time


async def can_use(ctx: commands.Context):
    if ctx.guild:
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


class Cog(commands.Cog):
    def __init__(self):
        self.emoji: str = "<:sadcowboy:1002608868360208565>"
        self.time: float = time.time()

    async def cog_before_invoke(self, ctx: commands.Context) -> None:
        if await can_use(ctx) or ctx.author.guild_permissions.administrator:
            return await super().cog_before_invoke(ctx)
        else:
            raise commands.errors.CheckFailure


class View(discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_quit(
        self,
        author: discord.User,
        guild: discord.Guild = None,
        delete_reference: bool = True,
        **kwargs,
    ):
        self.author = author
        self.delete_reference = delete_reference
        attributes = {
            "style": discord.ButtonStyle.red,
            "label": "Quit",
            "disabled": not guild,
        }
        attributes.update(**kwargs)
        button = discord.ui.Button(**attributes)
        button.callback = self.quit_callback
        return self.add_item(button)

    async def quit_callback(self, interaction: discord.Interaction):
        await self.quit(interaction, self.author, self.delete_reference)

    @classmethod
    async def quit(
        cls,
        interaction: discord.Interaction,
        author: discord.User = None,
        delete_reference: bool = True,
    ):
        if interaction.user != author:
            raise NotYourButton

        reference = interaction.message.reference
        if reference and delete_reference:
            try:
                msg = await interaction.channel.fetch_message(reference.message_id)
                await msg.delete()
            except:
                pass

        await interaction.message.delete()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        if iserror(error, NotYourButton):
            return await interaction.response.send_message(
                error.reason or "This is not your button !", ephemeral=True
            )

        if iserror(error, NoVoiceFound):
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
            icon_url=interaction.user.avatar.url,
        )

        view = subclasses.View()
        view.add_quit(interaction.user, interaction.guild)

        # Owner embed w full traceback
        await interaction.client.get_user(interaction.client.owner_id).send(embed=embed)

        # User error
        embed = discord.Embed(
            title=f":warning: {type(error).__qualname__}",
            description=f"> {' '.join(error.args)}" if len(error.args) > 0 else None,
        )
        return await interaction.response.send_message(embed=embed, view=view)

    async def on_timeout(self):
        self.clear_items()
