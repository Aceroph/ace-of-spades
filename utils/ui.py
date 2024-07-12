import time
from typing import TYPE_CHECKING, Union

import discord
from discord.ext import commands

from . import subclasses

if TYPE_CHECKING:
    from main import AceBot


class PartyMenu(subclasses.View):
    def __init__(self, bot: "AceBot", vcs: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.vcs = vcs
        self.edit_cd = commands.CooldownMapping.from_cooldown(
            2, 600, commands.BucketType.channel
        )

    class Embed(discord.Embed):
        def __init__(self, ctx: commands.Context, vcs: dict):
            super().__init__(color=discord.Color.gold())
            self.vc = ctx.author.voice.channel
            self.vcs = vcs
            self.title = f":loud_sound: {self.vc.name}"
            self.description = f"Owner : {ctx.bot.get_user(self.vcs[str(self.vc.id)]).mention}\nCreated : <t:{int(self.vc.created_at.timestamp())}:R>"

    async def check_ownership(
        self, ctx: Union[discord.Interaction, commands.Context], override: bool = False
    ):
        if isinstance(ctx, discord.Interaction):
            author, bot = ctx.user, ctx.client
        else:
            author, bot = ctx.author, ctx.bot

        vc = author.voice.channel

        if (
            override
            or str(vc.id) not in self.vcs.keys()
            or bot.get_user(self.vcs[str(vc.id)]) not in vc.members
        ):
            self.vcs[str(vc.id)] = author.id
            return author

        return author.id == self.vcs[str(vc.id)]

    def locked(self, interaction: discord.Interaction):
        return interaction.user.voice.channel.user_limit == 1

    @discord.ui.button(
        style=discord.ButtonStyle.grey, custom_id="Party:Lock", emoji="\N{LOCK}"
    )
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.user.voice.channel
        ownership = await self.check_ownership(
            interaction
        )  # Returns new owner if changed

        if ownership:
            # Cooldown
            cd = self.edit_cd.update_rate_limit(interaction.message)
            if cd:
                retry = int(time.time() + cd)
                await interaction.response.send_message(
                    f":clock1: You can't lock/unlock this channel for the moment, please try again in <t:{retry}:R>",
                    ephemeral=True,
                )
            else:
                locked = self.locked(interaction)
                # Unlock
                if locked:
                    await vc.edit(user_limit=None, name=vc.name.strip(None))
                    button.emoji = "\N{OPEN LOCK}"
                    await interaction.response.send_message(
                        ":unlock: Unlocked channel", ephemeral=True
                    )
                # Lock
                else:
                    await vc.edit(user_limit=1, name=f"{None} {vc.name}")
                    button.emoji = "\N{LOCK}"
                    await interaction.response.send_message(
                        ":lock: Locked channel", ephemeral=True
                    )

                # Update embed
                embed = interaction.message.embeds[0]
                embed.title = f":loud_sound:{' :lock:' if locked else ''} {vc.name}"
                if isinstance(ownership, Union[discord.User, discord.Member]):
                    embed.set_footer(f"Transfered ownership -> {ownership.mention}")

                await interaction.message.edit(embed=embed)

    async def edit_name(self, interaction: discord.Interaction):
        def is_author(msg: discord.Message):
            return msg.author == interaction.user

        msg: discord.Message = await self.bot.wait_for("message", check=is_author)
        cd = self.edit_cd.update_rate_limit(interaction.message)
        if cd:
            retry = int(time.time() + cd)
            await interaction.followup.send(
                f":clock1: You can't rename this channel for the moment, please try again in <t:{retry}:R>"
            )
        else:
            await interaction.followup.send(
                f":memo: Edited party: `{interaction.user.voice.channel.name} -> {msg.content}`"
            )
            await interaction.user.voice.channel.edit(
                name=f"{None if self.locked(interaction) else ''} {msg.content}"
            )

        embed = interaction.message.embeds[0].set_footer(text=None)
        embed.title = (
            f":loud_sound:{' :lock:' if self.locked(interaction) else ''} {msg.content}"
        )

        await interaction.message.edit(embed=embed)

    @discord.ui.button(
        style=discord.ButtonStyle.grey, custom_id="Party:Edit", emoji="\N{MEMO}"
    )
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.check_ownership(interaction):
            await interaction.response.defer()
            await interaction.message.edit(
                embed=interaction.message.embeds[0].set_footer(
                    text="Waiting for message..."
                )
            )
            await self.edit_name(interaction)
