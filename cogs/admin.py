from typing import Optional, Union, TYPE_CHECKING, Tuple, List
from utils import subclasses, sql_querries, misc
from discord.ext import commands
from tabulate import tabulate
import difflib
import discord
import time

if TYPE_CHECKING:
    from main import AceBot


class Admin(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{NAME BADGE}'
        self.bot = bot


    @commands.group(aliases=['perms', 'rights'], invoke_without_command=True)
    async def permissions(self, ctx: commands.Context, target: Union[discord.Member, discord.Role]=lambda ctx : ctx.author, channel: discord.TextChannel=None):
        """Displays a role or a user's permissions.
        
        `[target]` can be either a role or a member
        `[channel]` defaults to global permissions"""

        permissions = channel.permissions_for(target) if channel else target.permissions if isinstance(target, discord.Role) else target.guild_permissions
        embed = discord.Embed()
        embed.description = f"{misc.curve} {'for ' + channel.mention if channel else 'Globally'}"
        # If entity is role
        if isinstance(target, discord.Role):
            embed.title = f'Permissions for {target.name}'
            embed.color = target.color if target.color.value != 0 else discord.Color.from_str('#2b2d31')
            embed.add_field(name='`[i]` Information', value=f'{misc.space}role: {f"@everyone" if target.is_default() else target.mention}\n{misc.space}color : [{embed.color}](https://www.color-hex.com/color/{str(embed.color).strip("#")})') #add additional info
            # if len(members)
            members = "\n".join([f"{misc.space}{member.mention}" for member in target.members[:5]])
            old = embed.add_field(name=f'`{len(target.members)}` Members', value=f'{members}')

        # If entity is user/member
        else:
            embed.set_author(name=f'Permissions for {target.display_name}', icon_url=target.avatar.url)
            embed.color = target.top_role.color if target.top_role.color.value != 0 else discord.Color.from_str('#2b2d31')
            old = embed.add_field(name='`[u]` User Info', value=f'{misc.space}preset : {misc.Categories.get_preset(permissions)}\n{misc.space}top role : {target.top_role.mention}')
        
        # Select permissions category
        categories = [category for category in misc.Categories.categories() if len(misc.Categories.sort(permissions, category)) > 0]
        options = [discord.SelectOption(label=category) for category in categories]
        options.insert(0, discord.SelectOption(label=f'{"Role" if isinstance(target, discord.Role) else "User"} Info', value='Info'))
        select_category = discord.ui.Select(placeholder=f'Select a  category ({len(categories)})', options=options)
        async def category(interaction: discord.Interaction) -> None:
            if interaction.user == ctx.author:
                if select_category.values[0] == 'Info': # If Info is selected
                    return await interaction.response.edit_message(embed=old)
                
                embed = interaction.message.embeds[0] # If any category is selected
                embed.clear_fields()
                display_categories = '\n- '.join([p.replace('_', ' ').capitalize() for p in misc.Categories.sort(permissions, select_category.values[0])])
                embed.add_field(name=f'[p] {select_category.values[0]}', value=f"```\n- {display_categories}```")
                return await interaction.response.edit_message(embed=embed)
            else:
                return await interaction.response.send_message('This is not your instance !', ephemeral=True)
        select_category.callback = category

        # View stuff
        view = subclasses.View()
        view.add_item(select_category)
        view.add_quit(author=ctx.author)

        await ctx.reply(embed=embed, view=view, mention_author=False)
    
    
    @permissions.command(name="edit")
    @commands.has_guild_permissions(administrator=True)
    async def permissions_edit(self, ctx: commands.Context, target: Optional[Union[discord.Member, discord.Role]]=lambda ctx : ctx.author, channel: Optional[discord.TextChannel]=None, *, permissions: str):
        """Edits a member or a role's permissions.
        
        `[target]` can be either a role or a member
        `[channel]` defaults to global permissions
        
        e.g.
        ```
        perms edit @aceroph +view_channel -send_messages```"""

        changed_permissions = {}
        changelog = "```ansi"
        all_permissions = [p for p in dir(discord.Permissions) if not p.startswith('_') and not callable(getattr(discord.Permissions, p))]
        # Find permissions or add them to not found
        for perm in permissions.split():
            action = perm[0] if perm[0] in ['+', '-', '='] else '+'
            perm = perm[1:] if perm[0] in ['+', '-', '='] else perm
            for perm2 in all_permissions:
                ratio = difflib.SequenceMatcher(None, perm.casefold(), perm2.casefold()).ratio()
                if ratio >= 0.85:
                    match action:
                        case '+':
                            changelog += f"\n\u001b[0;32m[+] {perm2}\u001b[0m"
                            changed_permissions[perm2] = True
                        case '-':
                            changelog += f"\n\u001b[0;31m[-] {perm2}\u001b[0m"
                            changed_permissions[perm2] = False
                        case '=':
                            changelog += f"\n\u001b[0;30m[=] {perm2}\u001b[0m"
                            changed_permissions[perm2] = None
                    break

        if channel:
            await channel.set_permissions(target=target, overwrite=discord.PermissionOverwrite(**changed_permissions))
        else:
            if isinstance(target, discord.Role):
                await target.edit(permissions=discord.Permissions(**changed_permissions))
            else:
                return await ctx.reply(mention_author=False, embed=discord.Embed(title=":warning: Error while editing user", description="> Cannot edit a user's permissions globally !", color=discord.Color.red()))
        
        if len(changed_permissions) < 1:
            changelog += "\nNothing changed```"
        else:
            changelog += "```"

        embed = discord.Embed()
        embed.description = f"{misc.curve} {'in ' + channel.mention if channel else 'Globally'}"
        # If entity is role
        if isinstance(target, discord.Role):
            embed.title = f"Updated {target.name}"
            embed.color = target.color if target.color.value != 0 else discord.Color.from_str('#2b2d31')
            embed.add_field(name="`[p]` Changelog", value=changelog)
            
        # If entity is user/member
        else:
            embed.set_author(name=f"Updated {target.display_name}", icon_url=target.avatar.url)
            embed.color = target.top_role.color if target.top_role.color.value != 0 else discord.Color.from_str('#2b2d31')
            embed.add_field(name="`[p]` Changelog", value=changelog)
        
        await ctx.reply(embed=embed, mention_author=False)



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

        await ctx.reply(embed=embed, mention_author=False)


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
            embed = discord.Embed(color=discord.Color.blurple(), title=f'Cleaned up {ctx.channel.mention}', description=f"{misc.space}Deleted `{total}` message{'s' if total > 1 else ''}")
            for user, count in users.items():
                embed.add_field(name=f'{misc.tilde} @{user}', value=f"{misc.space}{misc.curve} `{count}` deletion{'s' if total > 1 else ''}", inline=False)
            
            if len(embed.fields) == 0:
                embed.description = 'No message deleted'

            # Time taken
            embed.set_footer(text=f'Took {time.time()-timer:.2f} s')
    
            await ctx.send(embed=embed, view=subclasses.View().add_quit(ctx.author, row=2))
    

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @cleanup.command(name='until')
    async def cleanup_until(self, ctx: commands.Context, message: int=None):
        """Cleans up the channel by removing bot responses.
        Will delete up to the replied message or if provided,
        to the given id."""
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
            embed = discord.Embed(color=discord.Color.blurple(), title=f"Cleaned up {ctx.channel.mention}", description=f"{misc.space}Deleted `{total}` message{'s' if total > 1 else ''}")
            for user, count in users.items():
                embed.add_field(name=f'{misc.tilde} @{user}', value=f"{misc.space}{misc.curve} `{count}` deletion{'s' if total > 1 else ''}", inline=False)
            
            if len(embed.fields) == 0:
                embed.description = 'No message deleted'

            # Time taken
            embed.set_footer(text=f'Took {time.time()-timer:.2f} s')
            
            await ctx.send(embed=embed, view=subclasses.View().add_quit(ctx.author, row=2))


    @commands.is_owner()
    @commands.command(name="reload", aliases=["r"])
    async def module_reload(self, ctx: commands.Context, cog: str):
        """Reloads the provided module if exists"""
        module: str = None
        # Find module name (eg. cogs.admin)
        for cg in self.bot.cogs:
            ratio = difflib.SequenceMatcher(None, cog.casefold(), cg.casefold()).ratio()
            if ratio >= 0.70:
                cog: commands.Cog = self.bot.get_cog(cg)
                module = cog.__module__
                break
        
        if not module:
            await ctx.message.add_reaction("\N{DOUBLE EXCLAMATION MARK}")
            embed = discord.Embed(title=":warning: ExtensionNotFound", description=f"> Couldn't find module : `{cog}`", color=discord.Color.red())
            return await ctx.reply(embed=embed, mention_author=False)
        
        timer = time.time()
        try:
            await self.bot.reload_extension(module)
        except Exception as error:
            await self.bot.error_handler(ctx, error)
            
        embed = discord.Embed(title=":gear: Reloaded Module", description=f">>> {cog.qualified_name}\n{misc.curve} reloaded `{len(cog.get_commands())}` commands", color=discord.Color.blurple())
        embed.set_footer(text=f"Took {(time.time() - timer)*1000:.2f}ms")
        await ctx.reply(embed=embed, mention_author=False)
    

    @commands.is_owner()
    @commands.command(name="load", aliases=["l"])
    async def module_load(self, ctx: commands.Context, cog: str):
        """Loads the provided module if exists"""
        module: str = None
        # Find module name (eg. cogs.admin)
        for cg in self.bot.cogs:
            ratio = difflib.SequenceMatcher(None, cog.casefold(), cg.casefold()).ratio()
            if ratio >= 0.70:
                cog: commands.Cog = self.bot.get_cog(cg)
                module = cog.__module__
                break
        
        if not module:
            await ctx.message.add_reaction("\N{DOUBLE EXCLAMATION MARK}")
            embed = discord.Embed(title=":warning: ExtensionNotFound", description=f"> Couldn't find module : `{cog}`", color=discord.Color.red())
            return await ctx.reply(embed=embed, mention_author=False)
        
        timer = time.time()
        try:
            await self.bot.load_extension(module)
        except Exception as error:
            await self.bot.error_handler(ctx, error)
            
        embed = discord.Embed(title=":gear: Loaded Module", description=f">>> {cog.qualified_name}\n{misc.curve} loaded `{len(cog.get_commands())}` commands", color=discord.Color.blurple())
        embed.set_footer(text=f"Took {(time.time() - timer)*1000:.2f}ms")
        await ctx.reply(embed=embed, mention_author=False)
    

    @commands.is_owner()
    @commands.command(name="unload", aliases=["u"])
    async def module_unload(self, ctx: commands.Context, cog: str):
        """Unloads the provided module if exists"""
        module: str = None
        # Find module name (eg. cogs.admin)
        for cg in self.bot.cogs:
            ratio = difflib.SequenceMatcher(None, cog.casefold(), cg.casefold()).ratio()
            if ratio >= 0.70:
                cog: commands.Cog = self.bot.get_cog(cg)
                module = cog.__module__
                break
        
        if not module:
            await ctx.message.add_reaction("\N{DOUBLE EXCLAMATION MARK}")
            embed = discord.Embed(title=":warning: ExtensionNotFound", description=f"> Couldn't find module : `{cog}`", color=discord.Color.red())
            return await ctx.reply(embed=embed, mention_author=False)
        
        timer = time.time()
        try:
            await self.bot.unload_extension(module)
        except Exception as error:
            await self.bot.error_handler(ctx, error)
            
        embed = discord.Embed(title=":gear: Unloaded Module", description=f">>> {cog.qualified_name}\n{misc.curve} unloaded `{len(cog.get_commands())}` commands", color=discord.Color.blurple())
        embed.set_footer(text=f"Took {(time.time() - timer)*1000:.2f}ms")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.is_owner()
    @commands.command()
    async def sql(self, ctx: commands.Context, *, command: str):
        """Executes SQL commands to the database"""
        async with self.bot.pool.acquire() as conn:
            r = await conn.fetchall(command) or await conn.execute(command)
            await conn.commit()
            
            if isinstance(r, list):
                r = discord.Embed(description=f'```\n{tabulate(headers=r[0].keys(), tabular_data=r)}```')
            else:
                r = discord.Embed(description='Executed !')
            
            await ctx.reply(embed=r, view=subclasses.View().add_quit(ctx.author), mention_author=False)
    

    @commands.command(aliases=["killyourself", "shutdown"])
    @commands.is_owner()
    async def kys(self, ctx: commands.Context) -> None:
        """Self-explanatory"""
        await ctx.reply("https://tenor.com/view/pc-computer-shutting-down-off-windows-computer-gif-17192330", mention_author=False)
        await self.bot.close()
    

    @commands.command(aliases=["src"])
    async def source(self, ctx: commands.Context, *, obj: str=None) -> None:
        """Get the source of any command or cog"""
        url = misc.git_source(self.bot, obj)

        if not url: # On error
            await ctx.reply(embed=discord.Embed(title=f'Failed to fetch {obj} :('), delete_after=10, mention_author=False)
        else:
            await ctx.reply(embed=discord.Embed(title=f'Source for {obj or "Bot"}', url=url), mention_author=False)


async def setup(bot):
    await bot.add_cog(Admin(bot))
