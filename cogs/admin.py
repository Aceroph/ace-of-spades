from typing import Optional, Union, TYPE_CHECKING, Callable

from discord.utils import MISSING
from utils import subclasses, sql_querries, misc
from discord.ext import commands
from tabulate import tabulate
import discord
import asyncio
import time

if TYPE_CHECKING:
    from main import AceBot

class PermsModal(discord.ui.Modal):
    def __init__(self, *, title: str) -> None:
        super().__init__(title=title)
    
    web = discord.ui.Button(style=discord.ButtonStyle.blurple, label='Open permissions manager', url='https://discordapi.com/permissions.html')
    perms = discord.ui.TextInput(label='Permissions :', style=discord.TextStyle.short, placeholder='Insert number provided by the website', required=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        permissions = discord.Permissions._from_value(int(self.perms.value))
        await interaction.response.send_message(content=[*permissions])


class Admin(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{NAME BADGE}'
        self.bot = bot


    @commands.group(aliases=['perms', 'rights'], invoke_without_command=True)
    async def permissions(self, ctx: commands.Context, entity: Union[discord.Member, discord.Role] = None, channel: Optional[discord.TextChannel] = None):
        """Outputs the permissions of any role or person in a webpage"""
        entity = entity if entity else ctx.author
        permissions = channel.permissions_for(entity) if channel else entity.permissions if isinstance(entity, discord.Role) else entity.guild_permissions

        embed = discord.Embed()
        # If entity is role
        if isinstance(entity, discord.Role):
            embed.title = f'Permissions for {entity.name}'
            embed.color = entity.color if entity.color.value != 0 else discord.Color.from_str('#2b2d31')
            embed.add_field(name='`[i]` Information', value=f'{misc.space}role: {f"@everyone" if entity.is_default() else entity.mention}\n{misc.space}color : [{embed.color}](https://www.color-hex.com/color/{str(embed.color).strip("#")})') #add additional info
            old = embed.add_field(name=f'`{len(entity.members)}` Members', value=f'{misc.space}{f'\n{misc.space}'.join([member.mention for member in entity.members])}')

        # If entity is user/member
        else:
            embed.set_author(name=f'Permissions for {entity.display_name}', icon_url=entity.avatar.url)
            embed.color = entity.top_role.color if entity.top_role.color.value != 0 else discord.Color.from_str('#2b2d31')
            old = embed.add_field(name='`[u]` User Info', value=f'{misc.space}preset : {misc.Categories.get_preset(permissions)}\n{misc.space}top role : {entity.top_role.mention}')
        
        # Select permissions category
        categories = [category for category in misc.Categories.categories() if len(misc.Categories.sort(permissions, category)) > 0]
        options = [discord.SelectOption(label=category) for category in categories]
        options.insert(0, discord.SelectOption(label=f'{"Role" if isinstance(entity, discord.Role) else "User"} Info', value='Info'))
        select_category = discord.ui.Select(placeholder=f'Select a  category ({len(categories)})', options=options)
        async def category(interaction: discord.Interaction) -> None:
            if interaction.user == ctx.author:
                if select_category.values[0] == 'Info': # If Info is selected
                    return await interaction.response.edit_message(embed=old)
                
                embed = interaction.message.embeds[0] # If any category is selected
                embed.clear_fields()
                embed.add_field(name=f'[p] {select_category.values[0]}', value=f"```\n- {'\n- '.join([p.replace('_', ' ').capitalize() for p in misc.Categories.sort(permissions, select_category.values[0])])}```")
                return await interaction.response.edit_message(embed=embed)
            else:
                return await interaction.response.send_message('This is not your instance !', ephemeral=True)
        select_category.callback = category

        # Edit permissions button
        edit_button = discord.ui.Button(style=discord.ButtonStyle.gray, label='Edit permissions', emoji='\N{MEMO}', disabled=True)
        
        async def edit_button_callback(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(PermsModal(title=f"Editing {entity.name if isinstance(entity, discord.Role) else entity.display_name}'s permissions"))

        edit_button.callback = edit_button_callback

        # View stuff
        view = subclasses.View()
        view.add_item(select_category)
        view.add_item(edit_button)
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.blurple, label='Permissions', url='https://discordapi.com/permissions.html'))
        view.add_quit(author=ctx.author)

        await ctx.reply(embed=embed, view=view)


    @commands.command()
    @commands.is_owner()
    @commands.guild_only()
    async def config(self, ctx: commands.Context) -> None:
        """Shows current guild's config"""
        config = await sql_querries.get_all(self.bot, ctx.guild.id)
        config = [[x[1], x[0]] for x in config]

        embed = discord.Embed(title=f"{ctx.guild.name}'s configuration", colour=discord.Color.blurple())
        embed.set_author(name="Guild Config", icon_url=self.bot.user.avatar.url)
        embed.description = f'```\n{tabulate(config, headers=["Key", "Value"], tablefmt="outline")}```'

        await ctx.send(embed=embed)


    @commands.guild_only()
    @commands.group(aliases=['clean'], invoke_without_command=True)
    async def cleanup(self, ctx: commands.Context, amount: int=25):
        """Cleans up the channel by removing bot responses.
        If an amount isn't specified, it'll default to 25 messages.
        Commands invoked by the user will also get deleted !"""
        async with ctx.typing():
            timer = time.time()

            # Get messages to delete
            to_delete: list[discord.Message] = []
            async for msg in ctx.channel.history(limit=amount + 1 if ctx.channel.permissions_for(ctx.author).manage_messages else 25 if amount + 1 > 25 else amount + 1):
                if msg.author.bot or msg.content.lower().startswith(('b.', 'a.', ctx.prefix.lower())):
                    to_delete.append(msg)
            
            await ctx.channel.delete_messages(to_delete, reason='Cleanup')

            # Count messages
            users: dict[str, int] = {}
            for msg in to_delete:
                name = msg.author.display_name
                if name not in users.keys():
                    users[name] = 1
                else:
                    users[name] += 1
            total = sum(list(users.values()))
            
            # Embed building
            embed = discord.Embed(color=discord.Color.blurple(), title=f'Cleaned up {ctx.channel.mention}', description=f'{misc.space}Deleted `{total}` message{'s' if total > 1 else ''}')
            for user, count in users.items():
                embed.add_field(name=f'{misc.tilde} @{user}', value=f'{misc.space}{misc.curve} `{count}` deletion{'s' if total > 1 else ''}', inline=False)
            
            if len(embed.fields) == 0:
                embed.description = 'No message deleted'

            # Time taken
            embed.set_footer(text=f'Took {time.time()-timer:.2f} s')
    
            await ctx.send(embed=embed, view=subclasses.View().add_quit(ctx.author, row=2))
    

    @commands.guild_only()
    @cleanup.command(name='until')
    async def cleanup_until(self, ctx: commands.Context, message: int=None):
        async with ctx.typing():
            # Get message refered or mentionned
            timer = time.time()
            message: discord.Message = self.bot.get_partial_messageable(id=message or ctx.message.reference.resolved.id or ctx.message.reference.message_id, guild_id=ctx.guild.id if ctx.guild else None)

            # Get messages to delete
            to_delete: list[discord.Message] = []
            async for msg in ctx.channel.history():
                if msg.created_at >= message.created_at:
                    if msg.author.bot or msg.content.lower().startswith(('b.', 'a.', ctx.prefix.lower())):
                        to_delete.append(msg)
                else:
                    break
            
            await ctx.channel.delete_messages(to_delete, reason='Cleanup')

            # Count messages
            users: dict[str, int] = {}
            for msg in to_delete:
                name = msg.author.display_name
                if name not in users.keys():
                    users[name] = 1
                else:
                    users[name] += 1
            total = sum(list(users.values()))
            
            # Embed building
            embed = discord.Embed(color=discord.Color.blurple(), title=f'Cleaned up {ctx.channel.mention}', description=f'{misc.space}Deleted `{total}` message{'s' if total > 1 else ''}')
            for user, count in users.items():
                embed.add_field(name=f'{misc.tilde} @{user}', value=f'{misc.space}{misc.curve} `{count}` deletion{'s' if total > 1 else ''}', inline=False)
            
            if len(embed.fields) == 0:
                embed.description = 'No message deleted'

            # Time taken
            embed.set_footer(text=f'Took {time.time()-timer:.2f} s')
            
            await ctx.send(embed=embed, view=subclasses.View().add_quit(ctx.author, row=2))


async def setup(bot):
    await bot.add_cog(Admin(bot))
