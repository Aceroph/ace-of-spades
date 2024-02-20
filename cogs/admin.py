from typing import Optional, Union, TYPE_CHECKING
from utils import subclasses, sql_querries
from discord.ext import commands
from tabulate import tabulate
import discord
import asyncio

if TYPE_CHECKING:
    from main import AceBot


class Admin(subclasses.Cog):
    def __init__(self, bot: 'AceBot'):
        super().__init__()
        self.emoji = '\N{NAME BADGE}'
        self.bot = bot


    @commands.group(aliases=['perms', 'rights'], invoke_without_command=True)
    async def permissions(self, ctx: commands.Context, object: Union[discord.Member, discord.Role] = None, channel: Optional[discord.TextChannel] = None):
        """Outputs the permissions of any role or person in a webpage"""
        channel = channel if channel else ctx.channel
        object = object if object else ctx.author
        icon = object.avatar.url if type(object) is discord.Member else self.bot.user.avatar.url
        permissions = channel.permissions_for(object)
        color = discord.Color.blurple() if isinstance(object, discord.Member) or object.color.value == 0 else object.color

        embed = discord.Embed(title="Chart of rights", description=f"{'Permissions' if isinstance(object, discord.Member) else 'Role permissions'} for {channel.mention}", color=color, url=f"https://discordapi.com/permissions.html#{permissions.value}")
        embed.set_author(name=object, icon_url=icon)
        embed.set_footer(text="Click on Chart of rights to view all permissions (Was too lazy to print them here)")

        await ctx.reply(embed=embed)

    @permissions.command(name="edit")
    @commands.is_owner()
    async def permissions_edit(self, ctx: commands.Context, role: discord.Role, channel: Optional[discord.TextChannel] = None, *, permissions: str):
        """Modify a role's permission for one or many channels"""
        channels = [channel] if channel else ctx.guild.text_channels
        changelog = ""
        
        async with ctx.channel.typing():
            for channel in channels:
                new_perms = dict(channel.permissions_for(role))

                for permission in permissions.split():
                    # split action (+/-) and permission
                    action = permission[0]
                    permission = permission[1:]

                    # edit permissions
                    match action:
                        case "+":
                            match permission:
                                case "*":
                                    new_perms = dict(discord.Permissions.all())
                                    changelog += "[+] All permissions\n"
                                case other:
                                    new_perms[other] = True
                                    changelog += f"[+] {other.replace('_', ' ').capitalize()}\n"

                        case "-":
                            match permission:
                                case "*":
                                    new_perms = dict(discord.Permissions.none())
                                    changelog += "[-] All permissions\n"
                                case other:
                                    new_perms[other] = False
                                    changelog += f"[-] {other.replace('_', ' ').capitalize()}\n"

                        case "=":
                            match permission:
                                case "*":
                                    new_perms = {perm[0]: None for perm in discord.Permissions.all()}
                                    changelog += "[=] All permissions\n"
                                case other:
                                    new_perms[other] = None
                                    changelog += f"[=] {permission.replace('_', ' ').capitalize()}\n"

                overwrite = discord.PermissionOverwrite(**new_perms)
                await channel.set_permissions(role, overwrite=overwrite)
                await asyncio.sleep(0.5)
        
        # embed
        color = discord.Color.blurple() if not isinstance(role, discord.Role) or role.color.value == 0 else role.color
        embed = discord.Embed(color=color, title="Permission manager", description=f"Updated roles for {role.name} {'in ' + channel.mention if len(channels) < 2 else 'globally'}\n```\n{changelog}```")
        embed.set_author(name=role.name, icon_url=self.bot.user.avatar.url)

        await ctx.reply(embed=embed)


    @commands.command()
    @commands.is_owner()
    async def config(self, ctx: commands.Context):
        """Shows current guild's config"""
        config = sql_querries.get_all(self.bot.connection, ctx.guild.id)
        config = [[x[1], x[2]] for x in config]

        embed = discord.Embed(title=f"{ctx.guild.name}'s configuration", colour=discord.Color.blurple())
        embed.set_author(name="Guild Config", icon_url=self.bot.user.avatar.url)
        embed.description = f'```\n{tabulate(config, headers=["Key", "Value"], tablefmt="outline")}```'

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
