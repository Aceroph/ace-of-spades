import discord
from discord.ext import commands
from main import AceBot
import time, datetime, pytz
from . import EMOJIS, subclasses, misc
import inspect

class ModuleEmbed(discord.Embed):
    def __init__(self, bot: AceBot):
        super().__init__(color=discord.Color.blurple())
        self.bot = bot
        self.set_footer(text=datetime.datetime.strftime(datetime.datetime.now(tz=pytz.timezone('US/Eastern')), "Today at %H:%M"))
        self.list_modules()
        self.set_thumbnail(url='https://static-00.iconduck.com/assets.00/cog-settings-icon-2048x1619-0lz5tnft.png')
        self.count = 0
    
    def list_modules(self, selected: subclasses.Cog=None):
        data = {'name': "Extensions", 'value': "\n".join([f"{self.bot.get_cog(name).emoji} {f'`{name}`' if selected and selected.qualified_name == name else name}" for name in self.bot.cogs]), 'inline': True}
        if len(self.fields) > 0:
            return self.set_field_at(0, **data)
        else:
            return self.insert_field_at(0, **data)

    async def module_info(self, cog: subclasses.Cog=None):
        if cog:
            # count lines for cog
            self.count = 0
            lines, _ = inspect.getsourcelines(cog.__class__)
            for line in lines:
                self.count += 1 if len(line.strip()) > 0 else 0

            data = {'name': cog.qualified_name + ' Module', 'value':f"Loaded\n⤷ <t:{int(cog.time)}:R>\n\nStats\n⤷ Commands used : {cog.cmds}\n⤷ Lines : {self.count}\n⤷ [Source]({await misc.git_source(self.bot, cog)})", 'inline': True}
            return self.set_field_at(1, **data) if len(self.fields) > 1 else self.insert_field_at(1, **data)
        elif len(self.fields) > 1:
            return self.remove_field(1)


class ModuleMenu(subclasses.View):
    def __init__(self, bot: AceBot, embed: ModuleEmbed):
        super().__init__(timeout=None)

        self.bot = bot
        self.embed = embed
        options = [discord.SelectOption(label=name, value=name, emoji=module.emoji) for name, module in self.bot.cogs.items()]
        self.add_item(self.ModuleSelect(options))
    
    class ModuleSelect(discord.ui.Select["ModuleMenu"]):
        def __init__(self, options):
            super().__init__(placeholder="Choose a module", custom_id="Module:Select", options=options, row=1)
        
        async def callback(self, interaction: discord.Interaction):
            cog = self.view.bot.get_cog(str(self.values[0]))
            embed: ModuleEmbed = self.view.embed
            await embed.module_info(cog)
            embed.list_modules(cog)

            return await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(style=discord.ButtonStyle.blurple, label="Reload", custom_id="Module:Reload", emoji=EMOJIS["repeat"], row=2)
    async def reload(self, interaction: discord.Interaction, button: discord.ui):
        if interaction.user.id == self.bot.owner_id:
            for child in self.children:
                module = None
                if isinstance(child, self.ModuleSelect) and child.values.__len__() > 0:
                    module = child.values[0]
                    break
            
            if module is not None:
                start = time.time()
                try:
                    await self.bot.reload_extension(f"cogs.{module.lower()}")
                    await interaction.response.send_message(f":repeat: Reloaded {module} `(Took around {round(time.time()-start, 4)}s)`", ephemeral=True)
                except Exception as err:
                    await interaction.response.send_message(f":warning: An error occured while trying to reload {module} ! `{err}`", ephemeral=True)
            else:
                await interaction.response.send_message(":warning: Did not select any module !", ephemeral=True)
        else:
            raise commands.errors.NotOwner


class PartyMenu(subclasses.View):
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
        