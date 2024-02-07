import discord
from main import AceBot
import json
import pathlib
import time

EMOJIS = json.load(open(pathlib.Path(__file__).parent / "emoji_map.json", "r"))

class ModuleSelect(discord.ui.Select):
    def __init__(self, bot: AceBot):
        self.bot = bot
        options = [discord.SelectOption(label=name, value=name, emoji=module.emoji) for name, module in bot.cogs.items()]

        super().__init__(placeholder="Choose a module", custom_id="ModuleSelect", options=options, row=1)
    
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
    
    @discord.ui.button(style=discord.ButtonStyle.blurple, label="Reload", custom_id="ModuleReload", emoji=EMOJIS["repeat"], row=2)
    async def reload(self, interaction: discord.Interaction, button: discord.ui):
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
        