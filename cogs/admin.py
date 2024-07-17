import difflib
import time
from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional, Union

import discord
from discord import app_commands
from discord.ext import commands
from tabulate import tabulate

from utils import misc, subclasses
from utils.errors import NotYourButton

from . import EXTENSIONS

if TYPE_CHECKING:
    from main import AceBot


class Admin(subclasses.Cog):
    def __init__(self, bot: "AceBot"):
        super().__init__(
            bot=bot,
            emoji="\N{NAME BADGE}",
        )

    @commands.group(aliases=["perms", "rights"], invoke_without_command=True)
    async def permissions(
        self,
        ctx: commands.Context,
        target: Union[discord.Member, discord.Role] = lambda ctx: ctx.author,
        channel: discord.TextChannel = None,
    ):
        """Displays a role or a user's permissions.

        `[target]` can be either a role or a member
        `[channel]` defaults to global permissions"""

        permissions = (
            channel.permissions_for(target)
            if channel
            else (
                target.permissions
                if isinstance(target, discord.Role)
                else target.guild_permissions
            )
        )
        embed = discord.Embed()
        embed.description = (
            f"{misc.curve} {'for ' + channel.mention if channel else 'Globally'}"
        )
        # If entity is role
        if isinstance(target, discord.Role):
            embed.title = f"Permissions for {target.name}"
            embed.color = (
                target.color
                if target.color.value != 0
                else discord.Color.from_str("#2b2d31")
            )
            embed.add_field(
                name="`[i]` Information",
                value=f'{misc.space}role: {f"@everyone" if target.is_default() else target.mention}\n{misc.space}color : [{embed.color}](https://www.color-hex.com/color/{str(embed.color).strip("#")})',
            )  # add additional info
            # if len(members)
            members = "\n".join(
                [f"{misc.space}{member.mention}" for member in target.members[:5]]
            )
            old = embed.add_field(
                name=f"`{len(target.members)}` Members", value=f"{members}"
            )

        # If entity is user/member
        else:
            embed.set_author(
                name=f"Permissions for {target.display_name}",
                icon_url=target.avatar.url,
            )
            embed.color = (
                target.top_role.color
                if target.top_role.color.value != 0
                else discord.Color.from_str("#2b2d31")
            )
            old = embed.add_field(
                name="`[u]` User Info",
                value=f"{misc.space}preset : {misc.Categories.get_preset(permissions)}\n{misc.space}top role : {target.top_role.mention}",
            )

        # Select permissions category
        options = [
            discord.SelectOption(label=category)
            for category in misc.Categories.categories()
        ]
        options.insert(
            0,
            discord.SelectOption(
                label=f'{"Role" if isinstance(target, discord.Role) else "User"} Info',
                value="Info",
            ),
        )
        select_category = discord.ui.Select(
            placeholder=f"Select a category", options=options
        )

        async def category(interaction: discord.Interaction) -> None:
            if interaction.user != ctx.author:
                raise NotYourButton

            if select_category.values[0] == "Info":  # If Info is selected
                return await interaction.response.edit_message(embed=old)

            embed = interaction.message.embeds[0]  # If any category is selected
            embed.clear_fields()
            symbol = lambda b: "\N{WHITE HEAVY CHECK MARK}" if b else "\N{CROSS MARK}"
            data = [
                [p[0].replace("_", " ").capitalize(), symbol(p[1])]
                for p in misc.Categories.sort(permissions, select_category.values[0])
            ]
            embed.add_field(
                name=f"[p] {select_category.values[0]}",
                value=f"```\n{tabulate(tabular_data=data, tablefmt='outline')}```",
            )
            return await interaction.response.edit_message(embed=embed)

        select_category.callback = category

        # View stuff
        view = subclasses.View()
        view.add_item(select_category)

        await ctx.reply(embed=embed, view=view, mention_author=False)

    @permissions.command(name="edit")
    @commands.has_guild_permissions(administrator=True)
    async def permissions_edit(
        self,
        ctx: commands.Context,
        target: Optional[Union[discord.Member, discord.Role]] = lambda ctx: ctx.author,
        channel: Optional[discord.TextChannel] = None,
        *,
        permissions: str,
    ):
        """Edits a member or a role's permissions.

        `[target]` can be either a role or a member
        `[channel]` defaults to global permissions

        e.g.
        ```
        perms edit @aceroph +view_channel -send_messages```"""

        changed_permissions = {}
        changelog = "```ansi"
        all_permissions = [
            p
            for p in dir(discord.Permissions)
            if not p.startswith("_") and not callable(getattr(discord.Permissions, p))
        ]
        # Find permissions or add them to not found
        for perm in permissions.split():
            action = perm[0] if perm[0] in ["+", "-", "="] else "+"
            perm = perm[1:] if perm[0] in ["+", "-", "="] else perm
            for perm2 in all_permissions:
                ratio = difflib.SequenceMatcher(
                    None, perm.casefold(), perm2.casefold()
                ).ratio()
                if ratio >= 0.85:
                    match action:
                        case "+":
                            changelog += f"\n\u001b[0;32m[+] {perm2}\u001b[0m"
                            changed_permissions[perm2] = True
                        case "-":
                            changelog += f"\n\u001b[0;31m[-] {perm2}\u001b[0m"
                            changed_permissions[perm2] = False
                        case "=":
                            changelog += f"\n\u001b[0;30m[=] {perm2}\u001b[0m"
                            changed_permissions[perm2] = None
                    break

        if channel:
            await channel.set_permissions(
                target=target,
                overwrite=discord.PermissionOverwrite(**changed_permissions),
            )
        else:
            if isinstance(target, discord.Role):
                await target.edit(
                    permissions=discord.Permissions(**changed_permissions)
                )
            else:
                return await ctx.reply(
                    embed=discord.Embed(
                        title=":warning: Error while editing user",
                        description="> Cannot edit a user's permissions globally !",
                        color=discord.Color.red(),
                    ),
                    mention_author=False,
                )

        if len(changed_permissions) < 1:
            changelog += "\nNothing changed```"
        else:
            changelog += "```"

        embed = discord.Embed()
        embed.description = (
            f"{misc.curve} {'in ' + channel.mention if channel else 'Globally'}"
        )
        # If entity is role
        if isinstance(target, discord.Role):
            embed.title = f"Updated {target.name}"
            embed.color = (
                target.color
                if target.color.value != 0
                else discord.Color.from_str("#2b2d31")
            )
            embed.add_field(name="`[p]` Changelog", value=changelog)

        # If entity is user/member
        else:
            embed.set_author(
                name=f"Updated {target.display_name}", icon_url=target.avatar.url
            )
            embed.color = (
                target.top_role.color
                if target.top_role.color.value != 0
                else discord.Color.from_str("#2b2d31")
            )
            embed.add_field(name="`[p]` Changelog", value=changelog)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.guild_only()
    @commands.hybrid_command(aliases=["clean"])
    async def cleanup(self, ctx: commands.Context, amount: int = 25):
        """Cleans up the channel by removing bot responses.
        If an amount isn't specified, it'll default to 25 messages."""
        async with ctx.typing():
            timer = time.time()
            amount = min(
                amount,
                25 if ctx.channel.permissions_for(ctx.author).manage_messages else 1000,
            )
            triggers = (".", "!", "?", ";", "b.", "a.")

            # Get messages to delete
            to_delete: list[discord.Message] = []
            if ctx.message.reference:
                reference: discord.Message = self.bot.get_partial_messageable(
                    id=ctx.message.reference.resolved.id
                    or ctx.message.reference.message_id,
                    guild_id=ctx.guild.id if ctx.guild else None,
                )
                history = ctx.channel.history(limit=amount, after=reference.created_at)
            else:
                history = ctx.channel.history(limit=amount)

            async for msg in history:
                if msg.author.bot or msg.content.startswith(triggers):
                    to_delete.append(msg)

            await ctx.channel.delete_messages(to_delete, reason="Cleanup")

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
            embed = discord.Embed(
                color=discord.Color.blurple(),
                title=f"Cleaned up {ctx.channel.mention}",
                description=f"{misc.space}Deleted `{total}` message{'s' if total > 1 else ''}",
            )
            for user, count in users.items():
                embed.add_field(
                    name=f"{misc.tilde} @{user}",
                    value=f"{misc.space}{misc.curve} `{count}` deletion{'s' if total > 1 else ''}",
                    inline=False,
                )

            if len(embed.fields) == 0:
                embed.description = "No message deleted"

            # Time taken
            embed.set_footer(text=f"Took {time.time()-timer:.2f} s")

            await ctx.send(embed=embed, delete_after=5)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.hybrid_command()
    async def purge(self, ctx: commands.Context, amount: int = 25):
        """Purges the channel, this cannot be undone !
        If an amount isn't specified, it'll default to 25 messages."""
        async with ctx.typing():
            timer = time.time()
            amount = min(amount, 1000)

            # Get messages to delete
            to_delete: list[discord.Message] = []
            if ctx.message.reference:
                reference: discord.Message = self.bot.get_partial_messageable(
                    id=ctx.message.reference.resolved.id
                    or ctx.message.reference.message_id,
                    guild_id=ctx.guild.id if ctx.guild else None,
                )
                history = ctx.channel.history(limit=amount, after=reference.created_at)
            else:
                history = ctx.channel.history(limit=amount)

            async for msg in history:
                to_delete.append(msg)

            await ctx.channel.delete_messages(to_delete, reason="Purge")

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
            embed = discord.Embed(
                color=discord.Color.blurple(),
                title=f"Purged {ctx.channel.mention}",
                description=f"{misc.space}Deleted `{total}` message{'s' if total > 1 else ''}",
            )
            for user, count in users.items():
                embed.add_field(
                    name=f"{misc.tilde} @{user}",
                    value=f"{misc.space}{misc.curve} `{count}` deletion{'s' if total > 1 else ''}",
                    inline=False,
                )

            if len(embed.fields) == 0:
                embed.description = "No message deleted"

            # Time taken
            embed.set_footer(text=f"Took {time.time()-timer:.2f} s")

            await ctx.send(embed=embed, delete_after=5)

    @commands.is_owner()
    @commands.command(name="reload", aliases=["r"])
    async def module_reload(self, ctx: commands.Context, extension: str):
        """Reloads the provided module if exists
        Accepts both short and long names, typo-friendly !
        e.g: `admin` or `cogs.admin`"""
        # RELOAD ALL
        if extension.casefold() in ["*", "all"]:
            reloaded = []
            for ext in EXTENSIONS:
                reloaded.append(ext)
                await self.bot.reload_extension(ext)

            timer = time.time()

            embed = discord.Embed(
                title=":gear: Reloaded All Modules",
                description=f">>> "
                + "\n".join(
                    sorted(
                        (ext for ext in reloaded),
                        key=lambda s: len(s),
                        reverse=True,
                    )
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=f"Took {(time.time() - timer)*1000:.2f}ms")
            return await ctx.reply(embed=embed, delete_after=5, mention_author=False)

        module: str = None
        # Find module name (eg. cogs.admin)
        for name in EXTENSIONS:
            extension_clean = (
                extension.casefold()
                if extension.startswith("cogs.")
                else "cogs." + extension.casefold()
            )
            ratio = difflib.SequenceMatcher(
                None, extension_clean, name.casefold()
            ).ratio()
            if ratio >= 0.85:
                module = name
                break

        if not module:
            await ctx.message.add_reaction("\N{DOUBLE EXCLAMATION MARK}")
            embed = discord.Embed(
                title=":warning: ExtensionNotFound",
                description=f"> Couldn't find module : `{extension}`",
                color=discord.Color.red(),
            )
            return await ctx.reply(embed=embed, delete_after=5, mention_author=False)

        timer = time.time()

        await self.bot.reload_extension(module)

        # Get cog if any
        cog: commands.Cog = None
        for cg in self.bot.cogs:
            ratio = difflib.SequenceMatcher(
                None, extension.casefold(), cg.casefold()
            ).ratio()
            if ratio >= 0.85:
                cog: commands.Cog = self.bot.get_cog(cg)
                break

        embed = discord.Embed(
            title=":gear: Reloaded Module",
            description=(
                f"> {module} - `{len(list(cog.walk_commands()))}` commands"
                if cog
                else f"> {module}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Took {(time.time() - timer)*1000:.2f}ms")
        await ctx.reply(embed=embed, delete_after=5, mention_author=False)

    @commands.is_owner()
    @commands.command(name="load", aliases=["l"])
    async def module_load(self, ctx: commands.Context, extension: str):
        """Loads the provided module if exists
        Accepts both short and long names, typo-friendly !
        e.g: `admin` or `cogs.admin`"""
        module: str = None
        # Find module name (eg. cogs.admin)
        for name in EXTENSIONS:
            extension_clean = (
                extension.casefold()
                if extension.startswith("cogs.")
                else "cogs." + extension.casefold()
            )
            ratio = difflib.SequenceMatcher(
                None, extension_clean, name.casefold()
            ).ratio()
            if ratio >= 0.85:
                module = name
                break

        if not module:
            await ctx.message.add_reaction("\N{DOUBLE EXCLAMATION MARK}")
            embed = discord.Embed(
                title=":warning: ExtensionNotFound",
                description=f"> Couldn't find module : `{extension}`",
                color=discord.Color.red(),
            )
            return await ctx.reply(embed=embed, delete_after=5, mention_author=False)

        timer = time.time()

        await self.bot.load_extension(module)

        # Get cog if any
        cog: commands.Cog = None
        for cg in self.bot.cogs:
            ratio = difflib.SequenceMatcher(
                None, extension.casefold(), cg.casefold()
            ).ratio()
            if ratio >= 0.85:
                cog: commands.Cog = self.bot.get_cog(cg)
                break

        embed = discord.Embed(
            title=":gear: Loaded Module",
            description=(
                f"> {module} - `{len(list(cog.walk_commands()))}` commands"
                if cog
                else f"> {module}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Took {(time.time() - timer)*1000:.2f}ms")
        await ctx.reply(embed=embed, delete_after=5, mention_author=False)

    @commands.is_owner()
    @commands.command(name="unload", aliases=["u"])
    async def module_unload(self, ctx: commands.Context, extension: str):
        """Unloads the provided module if exists
        Accepts both short and long names, typo-friendly !
        e.g: `admin` or `cogs.admin`"""
        module: str = None
        # Find module name (eg. cogs.admin)
        for name in EXTENSIONS:
            extension_clean = (
                extension.casefold()
                if extension.startswith("cogs.")
                else "cogs." + extension.casefold()
            )
            ratio = difflib.SequenceMatcher(
                None, extension_clean, name.casefold()
            ).ratio()
            if ratio >= 0.85:
                module = name
                break

        # Get cog if any
        cog: commands.Cog = None
        for cg in self.bot.cogs:
            ratio = difflib.SequenceMatcher(
                None, extension.casefold(), cg.casefold()
            ).ratio()
            if ratio >= 0.85:
                cog: commands.Cog = self.bot.get_cog(cg)
                break

        if not module:
            await ctx.message.add_reaction("\N{DOUBLE EXCLAMATION MARK}")
            embed = discord.Embed(
                title=":warning: ExtensionNotFound",
                description=f"> Couldn't find module : `{extension}`",
                color=discord.Color.red(),
            )
            return await ctx.reply(embed=embed, delete_after=5, mention_author=False)

        timer = time.time()

        await self.bot.unload_extension(module)

        embed = discord.Embed(
            title=":gear: Unloaded Module",
            description=(
                f"> {module} - `{len(list(cog.walk_commands()))}` commands"
                if cog
                else f"> {module}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Took {(time.time() - timer)*1000:.2f}ms")
        await ctx.reply(embed=embed, delete_after=5, mention_author=False)

    @commands.is_owner()
    @commands.command()
    async def sql(self, ctx: commands.Context, *, command: str):
        """Executes SQL commands to the database"""
        async with self.bot.pool.acquire() as conn:
            r = await conn.fetchall(command) or await conn.execute(command)
            await conn.commit()

            if isinstance(r, list):
                embed = discord.Embed(
                    description=f"```\n{tabulate(headers=r[0].keys(), tabular_data=r)}```"
                )
            else:
                embed = discord.Embed(description="Executed !")

            await ctx.reply(
                embed=embed,
                view=subclasses.View(),
                delete_after=20,
                mention_author=False,
            )

    @commands.command(
        aliases=[
            "killyourself",
            "shutdown",
            "unalive",
            "unaliveyourself",
        ]
    )
    @commands.is_owner()
    async def kys(self, ctx: commands.Context) -> None:
        """Self-explanatory"""
        await ctx.reply(
            "https://tenor.com/view/pc-computer-shutting-down-off-windows-computer-gif-17192330",
            mention_author=False,
            delete_after=5,
        )
        await self.bot.close()

    @app_commands.describe(entity="The module/command you want to steal")
    @commands.hybrid_command(aliases=["src"])
    async def source(self, ctx: commands.Context, *, entity: str = None) -> None:
        """Get the source of any command or cog"""
        url = misc.git_source(self.bot, entity)

        if not url:  # On error
            await ctx.reply(
                embed=discord.Embed(title=f"Failed to fetch {entity} :("),
                delete_after=5,
                mention_author=False,
            )
        else:
            await ctx.reply(
                embed=discord.Embed(title=f'Source for {entity or "Bot"}', url=url),
                mention_author=False,
            )

    @source.autocomplete("entity")
    async def source_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice]:
        cogs = [
            app_commands.Choice(name=f"[Cog] {cog}", value=cog)
            for cog in self.bot.cogs.keys()
            if current.casefold() in cog
        ]
        commands = [
            app_commands.Choice(
                name=f"[Cmd] {cmd.qualified_name.capitalize()}",
                value=cmd.qualified_name,
            )
            for cmd in self.bot.walk_commands()
            if current.casefold() in cmd.qualified_name
        ]
        if current.casefold() in "help":
            commands.append(app_commands.Choice(name="[Cmd] Help", value="help"))
        choices = sorted(cogs, key=lambda c: c.name, reverse=True) + sorted(
            commands, key=lambda c: c.name, reverse=True
        )
        return choices[:25]

    @commands.command()
    @commands.is_owner()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Guild],
        spec: Literal["list", "global", "*", "all", "local", "~", "^", "clear"] = None,
    ):
        if not guilds:
            match spec:
                case "list":

                    async def mentions(guild: int = None):
                        mentions = set()
                        for cmd in await self.bot.tree.fetch_commands(guild=guild):
                            if len(cmd.options) > 0 and isinstance(
                                cmd.options[0], app_commands.AppCommandGroup
                            ):
                                for sub in cmd.options:
                                    mentions.add(sub.mention)
                            else:
                                mentions.add(cmd.mention)
                        return mentions

                    global_mentions = await mentions()
                    local_mentions = await mentions(guild=ctx.guild)

                    embed = discord.Embed(
                        title="App Commands", color=discord.Color.blurple()
                    )
                    embed.add_field(
                        name=f"Globally",
                        value="\n".join(global_mentions) or "`None`",
                    )
                    embed.add_field(
                        name=f"Locally",
                        value="\n".join(local_mentions) or "`None`",
                    )
                    return await ctx.reply(embed=embed, mention_author=False)

                case "~" | "local":
                    synced = await ctx.bot.tree.sync(guild=ctx.guild)
                case "*", "all":
                    ctx.bot.tree.copy_global_to(guild=ctx.guild)
                    synced = await ctx.bot.tree.sync(guild=ctx.guild)
                case "^" | "clear":
                    ctx.bot.tree.clear_commands(guild=ctx.guild)
                    await ctx.bot.tree.sync(guild=ctx.guild)
                    synced = []
                case _:
                    synced = await ctx.bot.tree.sync()

            await ctx.reply(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}",
                mention_author=False,
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.reply(
            f"Synced the tree to {ret}/{len(guilds)}.", mention_author=False
        )

    @commands.is_owner()
    @commands.guild_only()
    @commands.hybrid_command(aliases=["config", "cfg"])
    @app_commands.describe(
        module="The module to configure",
        setting="The setting to update or view",
        value="The new value for the given setting",
    )
    async def settings(
        self,
        ctx: commands.Context,
        module: Annotated[subclasses.Cog, misc.Module],
        setting: Optional[str] = None,
        value: Optional[str] = None,
    ):
        """Configure a module"""

        # Formats value
        def format_value(value: Any, annotation: Any, default: Any = None) -> str:
            if not value:
                return f"`{default}`" if default is not None else "`None`"

            if issubclass(annotation, discord.abc.GuildChannel):
                return self.bot.get_channel(int(value)).mention
            else:
                return f"`{value}`"

        ## Show config
        if not value:
            config = {
                _name: _setting.default for _name, _setting in module.config.items()
            }
            async with self.bot.pool.acquire() as conn:
                if not setting:
                    config.update(
                        {
                            row[0].split(":")[1]: row[1]
                            for row in await conn.fetchall(
                                "SELECT key, value FROM guildConfig WHERE key LIKE :key AND id = :id;",
                                {
                                    "id": ctx.guild.id,
                                    "key": f"{module.qualified_name}:%",
                                },
                            )
                        }
                    )
                else:
                    config = {
                        row[0].split(":")[1]: row[1]
                        for row in await conn.fetchall(
                            "SELECT key, value FROM guildConfig WHERE key LIKE :key AND id = :id;",
                            {
                                "id": ctx.guild.id,
                                "key": f"{module.qualified_name}:{setting}",
                            },
                        )
                    }

            embed = discord.Embed(
                title=f"\N{GEAR}\N{VARIATION SELECTOR-16} Config for {module.qualified_name}",
                description="",
                color=discord.Color.blurple(),
            )
            embed.description = "\n".join(
                [
                    f"{misc.space}{_setting.replace('_', ' ')}: {format_value(_value, module.config[_setting].annotation, module.config[_setting].default)}"
                    for _setting, _value in config.items()
                ]
            )

            return await ctx.reply(embed=embed, mention_author=False)

        ## Set config
        async with self.bot.pool.acquire() as conn:
            if value.casefold() in {"none", "false", "no", "0"}:
                await conn.execute(
                    "DELETE FROM guildConfig WHERE key = :key AND id = :id;",
                    {"key": f"{module.qualified_name}:{setting}", "id": ctx.guild.id},
                )
                value = None
            else:
                # Convert value
                value: module.config[setting].annotation = (
                    await commands.run_converters(
                        ctx,
                        module.config[setting].annotation,
                        value,
                        commands.Parameter,
                    )
                )

                # Get id incase its a discord object
                value = getattr(value, "id", value)

                await conn.execute(
                    "INSERT INTO guildConfig (id, key, value) VALUES (:id, :key, :value) ON CONFLICT(id, key) DO UPDATE SET value = :value;",
                    {
                        "id": ctx.guild.id,
                        "key": f"{module.qualified_name}:{setting}",
                        "value": value,
                    },
                )

        embed = discord.Embed(
            title=f"\N{GEAR}\N{VARIATION SELECTOR-16} Updated config for {module.qualified_name}",
            description=f"{setting.replace('_', ' ')} -> {format_value(value, module.config[setting].annotation, module.config[setting].default)}",
            color=discord.Color.blurple(),
        )
        return await ctx.reply(embed=embed, mention_author=False)

    @settings.autocomplete("module")
    async def settings_module(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in self.bot.cogs.keys()
            if current.strip() == "" or name.casefold().startswith(current.casefold())
        ]

    @settings.autocomplete("setting")
    async def settings_setting(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice]:
        return [
            app_commands.Choice(name=setting, value=setting)
            for setting in self.bot.get_cog(interaction.namespace.module).config.keys()
            if current.strip() == ""
            or setting.casefold().startswith(current.casefold())
        ]

    @settings.autocomplete("value")
    async def settings_value(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice]:
        annotation = (
            self.bot.get_cog(interaction.namespace.module)
            .config[interaction.namespace.setting]
            .annotation
        )

        # True/False
        if issubclass(annotation, bool):
            return [
                app_commands.Choice(name=option, value=option)
                for option in ["True", "False"]
            ]

        # Text channel
        if issubclass(annotation, (discord.TextChannel, discord.ForumChannel)):
            channels = interaction.guild.text_channels + interaction.guild.forums
            return sorted(
                [
                    app_commands.Choice(
                        name="\N{SPEECH BALLOON} " + channel.name, value=channel.name
                    )
                    for channel in channels
                    if current.strip() == ""
                    or channel.name.casefold().startswith(current.casefold())
                ][:25],
                key=lambda c: c.name,
            )

        # Voice channel
        if issubclass(annotation, (discord.VoiceChannel, discord.StageChannel)):
            channels = (
                interaction.guild.voice_channels + interaction.guild.stage_channels
            )
            return sorted(
                [
                    app_commands.Choice(
                        name="\N{SPEAKER WITH THREE SOUND WAVES} " + channel.name,
                        value=channel.name,
                    )
                    for channel in channels
                    if current.strip() == ""
                    or channel.name.casefold().startswith(current.casefold())
                ][:25],
                key=lambda c: c.name,
            )


async def setup(bot):
    await bot.add_cog(Admin(bot))
