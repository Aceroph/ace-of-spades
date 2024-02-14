import discord
from discord.ext import commands
from main import AceBot
import time
import json
import pathlib

EMOJIS = json.load(open(pathlib.Path(__file__).parent / "emoji_map.json", "r"))


class ModuleSelect(discord.ui.Select):
    def __init__(self, bot: AceBot):
        self.bot = bot
        options = [discord.SelectOption(label=name, value=name, emoji=module.emoji) for name, module in bot.cogs.items()]

        super().__init__(placeholder="Choose a module", custom_id="Module:Select", options=options, row=1)
    
    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        cog = self.bot.get_cog(str(self.values[0]))

        # embeded data
        data = {"name": self.values[0] + " Module", "value": f"⤷ <t:{int(cog.time)}:R>\n\n__Stats__ :\n-> Total : {cog.cmds}", "inline": True}

        if embed.fields.__len__() == 2:
            embed.set_field_at(index=1, **data)
        else:
            embed.add_field(**data)

        return await interaction.response.edit_message(embed=embed)


class ModuleMenu(discord.ui.View):
    def __init__(self, bot: AceBot):
        super().__init__(timeout=None)

        self.bot = bot
        self.add_item(ModuleSelect(bot))
    
    @discord.ui.button(style=discord.ButtonStyle.blurple, label="Reload", custom_id="Module:Reload", emoji=EMOJIS["repeat"], row=2)
    async def reload(self, interaction: discord.Interaction, button: discord.ui):
        if interaction.user.id == self.bot.owner_id:
            for child in self.children:
                module = None
                if isinstance(child, ModuleSelect) and child.values.__len__() > 0:
                    module = child.values[0]
                    break
            
            if module is not None:
                start = time.time()
                try:
                    await self.bot.reload_extension(f"cogs.{module.lower()}")
                    await interaction.response.send_message(f":repeat: Reloaded *{module}* (Took around {round(time.time()-start, 4)}s)", ephemeral=True)
                except Exception as err:
                    await interaction.response.send_message(f":warning: An error occured while trying to reload *{module}* ! `{err}`", ephemeral=True)
            else:
                await interaction.response.send_message("Did not select any module !", ephemeral=True)
        else:
            raise commands.NotOwner


class PartyMenu(discord.ui.View):
    def __init__(self, bot: AceBot, vcs):
        super().__init__(timeout=None)

        self.bot = bot
        self.vcs = vcs
        self.edit_cd = commands.CooldownMapping.from_cooldown(2, 600, commands.BucketType.channel)

    def check_ownership(self, interaction: discord.Interaction):
        return interaction.user.id == self.vcs[str(interaction.user.voice.channel.id)]
    
    def is_locked(self, interaction: discord.Interaction):
        return interaction.user.voice.channel.user_limit == 1
    
    @discord.ui.button(style=discord.ButtonStyle.grey, custom_id="Party:Lock", emoji=EMOJIS["lock"])
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel
        if self.check_ownership(interaction):
            cd = self.edit_cd.update_rate_limit(interaction.message)
            if cd:
                retry = int(time.time() + cd)
                await interaction.response.send_message(f":clock1: You can't lock/unlock this channel for the moment, please try again in <t:{retry}:R>", ephemeral=True)
            else:
                if self.is_locked(interaction):
                    await channel.edit(user_limit=None, name=channel.name.strip(EMOJIS["lock"]))
                    button.emoji = EMOJIS["lock"]
                    await interaction.response.send_message(":unlock: Unlocked channel", ephemeral=True)
                else:
                    await channel.edit(user_limit=1, name=f"{EMOJIS['lock']} {channel.name}")
                    button.emoji = EMOJIS["unlock"]
                    await interaction.response.send_message(":lock: Locked channel", ephemeral=True)
    
    async def edit_name(self, interaction: discord.Interaction):
        def is_author(msg: discord.Message):
            return msg.author == interaction.user
        
        msg: discord.Message = await self.bot.wait_for('message', check=is_author)
        cd = self.edit_cd.update_rate_limit(interaction.message)
        if cd:
            retry = int(time.time() + cd)
            await interaction.followup.send(f":clock1: You can't rename this channel for the moment, please try again in <t:{retry}:R>", ephemeral=True)
        else:
            await interaction.followup.send(f":memo: Edited party: `{interaction.user.voice.channel.name} -> {msg.content}`", ephemeral=True)
            await interaction.user.voice.channel.edit(name=f"{EMOJIS['lock'] if self.is_locked(interaction) else ''} {msg.content}")
        embed = interaction.message.embeds[0].set_footer(text=None)
        embed.title = f":loud_sound: {msg.content}"
        await interaction.message.edit(embed=embed)

    @discord.ui.button(style=discord.ButtonStyle.grey, custom_id="Party:Edit", emoji=EMOJIS["memo"])
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.check_ownership(interaction):
            await interaction.response.defer()
            await interaction.message.edit(embed=interaction.message.embeds[0].set_footer(text="Waiting for message..."))
            await self.edit_name(interaction)
        