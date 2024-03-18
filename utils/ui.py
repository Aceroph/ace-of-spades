from typing import List, Union, TYPE_CHECKING
from discord.ext import commands
from . import subclasses, misc
from cogs import errors
import datetime
import discord
import inspect
import time
import pytz

if TYPE_CHECKING:
    from main import AceBot


class ModuleMenu(subclasses.View):
    def __init__(self, bot: 'AceBot'):
        super().__init__(timeout=None)
        self.bot = bot
        options = [discord.SelectOption(label=name, value=name, emoji=module.emoji) for name, module in self.bot.cogs.items()]
        self.add_item(self.Select(options))
    
    class Embed(discord.Embed):
        def __init__(self, bot: 'AceBot'):
            super().__init__(color=discord.Color.blurple())
            self.list_modules(bot)
            self.set_footer(text=datetime.datetime.strftime(datetime.datetime.now(tz=pytz.timezone('US/Eastern')), "Today at %H:%M"))
            self.set_thumbnail(url='https://static-00.iconduck.com/assets.00/cog-settings-icon-2048x1619-0lz5tnft.png')
            self.count = 0
        
        @classmethod
        def from_embed(cls, bot: 'AceBot', embed: discord.Embed):
            return cls(bot).from_dict(embed.to_dict())

        def list_modules(self, bot: 'AceBot', selected: subclasses.Cog=None):
            data = {'name': "Extensions", 'value': "\n".join([f"{bot.get_cog(name).emoji} {f'`{name}`' if selected and selected.qualified_name == name else name}" for name in bot.cogs]), 'inline': True}
            if len(self.fields) > 0:
                return self.set_field_at(0, **data)
            else:
                return self.insert_field_at(0, **data)

        def module_info(self, bot: 'AceBot', cog: subclasses.Cog=None):
            if cog:
                # count lines for cog
                self.count = 0
                lines, _ = inspect.getsourcelines(cog.__class__)
                for line in lines:
                    self.count += 1 if len(line.strip()) > 0 else 0

                data = {'name': cog.qualified_name + ' Module', 'value':f"Loaded\n⤷ <t:{int(cog.time)}:R>\n\nStats\n⤷ Commands used : {cog.cmds}\n⤷ Lines : {self.count}\n⤷ [Source]({misc.git_source(bot, cog)})", 'inline': True}
                return self.set_field_at(1, **data) if len(self.fields) > 1 else self.insert_field_at(1, **data)
            elif len(self.fields) > 1:
                return self.remove_field(1)

    class Select(discord.ui.Select["ModuleMenu"]):
        def __init__(self, options):
            super().__init__(placeholder="Choose a module", custom_id="Module:Select", options=options, row=1)
        
        async def callback(self, interaction: discord.Interaction):
            cog = self.view.bot.get_cog(str(self.values[0]))
            embed = self.view.Embed.from_embed(self.view.bot, interaction.message.embeds[0])
            embed.module_info(interaction.client, cog)
            embed.list_modules(interaction.client, cog)

            return await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(style=discord.ButtonStyle.blurple, label="Reload", custom_id="Module:Reload", emoji='\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}', row=2)
    async def reload(self, interaction: discord.Interaction, button: discord.ui.Button):
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
    def __init__(self, bot: 'AceBot', vcs: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.vcs = vcs
        self.edit_cd = commands.CooldownMapping.from_cooldown(2, 600, commands.BucketType.channel)
    
    class Embed(discord.Embed):
        def __init__(self, ctx: commands.Context, vcs: dict):
            super().__init__(color=discord.Color.gold())
            self.vc = ctx.author.voice.channel
            self.vcs = vcs
            self.title = f":loud_sound: {self.vc.name}"
            self.description = f"Owner : {ctx.bot.get_user(self.vcs[str(self.vc.id)]).mention}\nCreated : <t:{int(self.vc.created_at.timestamp())}:R>"
    
    async def check_ownership(self, ctx: Union[discord.Interaction, commands.Context], override: bool=False):
        if isinstance(ctx, discord.Interaction):
            author, bot = ctx.user, ctx.client
        else:
            author, bot = ctx.author, ctx.bot
    
        vc = author.voice.channel

        if override or str(vc.id) not in self.vcs.keys() or bot.get_user(self.vcs[str(vc.id)]) not in vc.members:
            self.vcs[str(vc.id)] = author.id
            return author
    
        return author.id == self.vcs[str(vc.id)]

    def locked(self, interaction: discord.Interaction):
        return interaction.user.voice.channel.user_limit == 1

    @discord.ui.button(style=discord.ButtonStyle.grey, custom_id="Party:Lock", emoji='\N{LOCK}')
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.user.voice.channel
        ownership = await self.check_ownership(interaction) # Returns new owner if changed

        if ownership:
            # Cooldown
            cd = self.edit_cd.update_rate_limit(interaction.message)
            if cd:
                retry = int(time.time() + cd)
                await interaction.response.send_message(f":clock1: You can't lock/unlock this channel for the moment, please try again in <t:{retry}:R>", ephemeral=True)
            else:
                locked = self.locked(interaction)
                # Unlock
                if locked:
                    await vc.edit(user_limit=None, name=vc.name.strip(None))
                    button.emoji = '\N{OPEN LOCK}'
                    await interaction.response.send_message(":unlock: Unlocked channel", ephemeral=True)
                # Lock
                else:
                    await vc.edit(user_limit=1, name=f"{None} {vc.name}")
                    button.emoji = '\N{LOCK}'
                    await interaction.response.send_message(":lock: Locked channel", ephemeral=True)
                
                # Update embed
                embed = interaction.message.embeds[0]
                embed.title = f":loud_sound:{' :lock:' if locked else ''} {vc.name}"
                if isinstance(ownership, Union[discord.User, discord.Member]):
                    embed.set_footer(f"Transfered ownership -> {ownership.mention}")
                
                await interaction.message.edit(embed=embed)
    
    async def edit_name(self, interaction: discord.Interaction):
        def is_author(msg: discord.Message):
            return msg.author == interaction.user
        
        msg: discord.Message = await self.bot.wait_for('message', check=is_author)
        cd = self.edit_cd.update_rate_limit(interaction.message)
        if cd:
            retry = int(time.time() + cd)
            await interaction.followup.send(f":clock1: You can't rename this channel for the moment, please try again in <t:{retry}:R>")
        else:
            await interaction.followup.send(f":memo: Edited party: `{interaction.user.voice.channel.name} -> {msg.content}`")
            await interaction.user.voice.channel.edit(name=f"{None if self.locked(interaction) else ''} {msg.content}")

        embed = interaction.message.embeds[0].set_footer(text=None)
        embed.title = f":loud_sound:{' :lock:' if self.locked(interaction) else ''} {msg.content}"

        await interaction.message.edit(embed=embed)

    @discord.ui.button(style=discord.ButtonStyle.grey, custom_id="Party:Edit", emoji='\N{MEMO}')
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.check_ownership(interaction):
            await interaction.response.defer()
            await interaction.message.edit(embed=interaction.message.embeds[0].set_footer(text="Waiting for message..."))
            await self.edit_name(interaction)

class HelpView(subclasses.View):
    def __init__(self, bot: 'AceBot', context: commands.Context):
        super().__init__(timeout=None)
        self.add_quit(author=context.author)
        self.bot = bot
        self.context = context
        self.old = None
        
    async def filter_commands(self, commands: List[commands.Command]):
        filtered_commands = []
        for command in commands:
            try:
                if await command.can_run(self.context):
                    filtered_commands.append(command)
            except:
                pass
        return filtered_commands

    @discord.ui.button(label="Show commands", style=discord.ButtonStyle.grey, custom_id="Help:ShowCommands", emoji='\N{INFORMATION SOURCE}')
    async def show(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.context.author != interaction.user:
            raise errors.NotYourButton

        if button.label == 'Show commands':
            self.old = interaction.message.embeds[0]
            embed = discord.Embed(color=discord.Color.blurple())
            embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Documents_icon_-_noun_project_5020_-_white.svg/1200px-Documents_icon_-_noun_project_5020_-_white.svg.png")
            embed.set_author(name=f"{self.context.author.display_name}: Help", icon_url=self.context.author.avatar.url)

            # Modules & Commands
            for name, module in self.bot.cogs.items():
                # Filter commands
                filtered_commands = await self.filter_commands(module.get_commands())
                cmds = [f'`{command.qualified_name}`' for command in filtered_commands]
                embed.add_field(name=f"{module.emoji} {name} - {len(cmds)}", value=' '.join(cmds), inline=False) if len(cmds) > 0 else None

            button.label = 'Back to help'
            return await interaction.response.edit_message(embed=embed, view=self)
        else:
            button.label = 'Show commands'
            return await interaction.response.edit_message(embed=self.old, view=self)
