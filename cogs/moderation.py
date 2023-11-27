from discord.ext import commands
import discord
from typing import Union

class PermissionSelect(discord.ui.Select):
    def __init__(self, categories, obj):
        self.categories = categories
        self.obj = obj
        self.emojis = {
            "All permissions": "*️⃣",
            "General": "🏠",
            "Membership": "🧍",
            "Elevated": "🚨",
            "Text": "💬",
            "Voice": "🗣️"
        }
        options = [discord.SelectOption(label=category, emoji=self.emojis[category]) for category in categories.keys()]
        super().__init__(max_values=1, min_values=1, options=options)
    
    async def page(self, page):
        items = self.categories[page]
        e = discord.Embed(color=discord.Color.blurple(), title=f"{self.obj}'s rights")
        e.add_field(name=f"{self.emojis[page]} {page} ({len(items)})", value="-> " + "\n-> ".join(items).replace("_", " ") if items != [] else "No rights in sight sergeant !")
        return e

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=await self.page(self.values[0]))


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command()
    async def perms(self, ctx: commands.Context, object: Union[discord.Member, discord.Role]=None):
        perms = ctx.channel.permissions_for(object) if object else ctx.channel.permissions_for(ctx.author)
        categories = {
            "General": [x if y else None for x, y in iter(discord.permissions.Permissions.general())],
            "Membership": [x if y else None for x, y in iter(discord.permissions.Permissions.membership())],
            "Elevated": [x if y else None for x, y in iter(discord.permissions.Permissions.elevated())],
            "Text": [x if y else None for x, y in iter(discord.permissions.Permissions.text())],
            "Voice": [x if y else None for x, y in iter(discord.permissions.Permissions.voice())]
            }
        output = {"All permissions": []}
        for category in categories:
            output[category] = []
            for perm, value in iter(perms):
                if perm in categories[category] and value:
                    output[category].append(perm)
                    output["All permissions"].append(perm)

        view = discord.ui.View()
        select = PermissionSelect(output, object.name if object else ctx.author.name)
        view.add_item(select)

        await ctx.reply(embed=await select.page("General"), view=view)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
