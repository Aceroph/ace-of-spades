import json
import re
from io import StringIO
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils import errors, misc, subclasses

if TYPE_CHECKING:
    from main import AceBot


HEX_REGEX = re.compile(r"^(#|0x) ?([a-f\d]{6}|[a-f\d]{3})$", re.IGNORECASE)

RGB_REGEX = re.compile(r"^(rgb) ?\([\d]{1,3}, ?[\d]{1,3}, ?[\d]{1,3} ?\)$")


class OptionalTextInput(discord.ui.TextInput):
    def __init__(
        self,
        label: str,
        style: discord.TextStyle = discord.TextStyle.short,
        placeholder: str | None = None,
        max_length: int = 256,
    ) -> None:
        super().__init__(
            label=label,
            style=style,
            placeholder=placeholder,
            required=False,    # subclass just cuz of this one attribute :verycool:
            max_length=max_length
        )


class EditText(discord.ui.Modal):
    _author = OptionalTextInput(
        label="Author name (256 characters)",
        placeholder="Leave empty for none",
    )
    _title = OptionalTextInput(
        label="Title (256 characters)",
        placeholder="Leave empty for none",
    )
    _description = OptionalTextInput(
        label="Description (4096 characters)",
        placeholder="Leave empty for none",
        style=discord.TextStyle.paragraph,
        max_length=4000,
    )
    _footer = OptionalTextInput(
        label="Footer (2048 characters)",
        placeholder="Leave empty for none",
        style=discord.TextStyle.paragraph,
        max_length=2048,
    )

    def __init__(self, builder: "EmbedBuilder") -> None:
        super().__init__(title="Edit text", custom_id="embedbuilder:text")
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Author name
        if self._author.value != "":
            if self.builder.changes.get("author"):
                self.builder.changes["author"]["name"] = self._author.value
            else:
                self.builder.changes["author"] = {"name": self._author.value}

        # Title
        if self._title.value != "":
            self.builder.changes["title"] = self._title.value

        # Description
        if self._description.value != "":
            self.builder.changes["description"] = self._description.value

        # Footer text
        if self._footer.value != "":
            if self.builder.changes.get("footer"):
                self.builder.changes["footer"]["text"] = self._footer.value
            else:
                self.builder.changes["footer"] = {"text": self._footer.value}

        await self.builder.update()
        return await interaction.response.defer()


class EditImages(discord.ui.Modal):
    _author = OptionalTextInput(
        label="Author icon url",
        placeholder="Leave empty for none (Supports user IDs)",
    )
    _thumbnail = OptionalTextInput(
        label="Thumbnail url",
        placeholder="Leave empty for none (Supports user IDs)",
    )
    _image = OptionalTextInput(
        label="Large image url",
        placeholder="Leave empty for none (Supports user IDs)",
    )
    _footer = OptionalTextInput(
        label="Footer icon url",
        placeholder="Leave empty for none (Supports user IDs)",
    )

    def __init__(self, builder: "EmbedBuilder") -> None:
        super().__init__(title="Edit images", custom_id="embedbuilder:images")
        self.builder = builder

    def get_image(self, text: str) -> str:
        # User ID
        userid = re.fullmatch(r"^[0-9]{15,21}$", text)
        if userid:
            user = self.builder.bot.get_user(int(userid.string))
            if user is not None:
                return user.display_avatar.url
        return None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Author icon url
        if self._author.value != "":
            if self.builder.changes.get("author"):
                self.builder.changes["author"]["icon_url"] = self.get_image(
                    self._author.value
                )
            else:
                self.builder.changes["author"] = {
                    "icon_url": self.get_image(self._author.value)
                }

        # Footer icon url
        if self._footer.value != "":
            if self.builder.changes.get("footer"):
                self.builder.changes["footer"]["icon_url"] = self.get_image(
                    self._footer.value
                )
            else:
                self.builder.changes["footer"] = {
                    "icon_url": self.get_image(self._footer.value)
                }

        # Thumbnail url
        if self._thumbnail.value != "":
            self.builder.changes["thumbnail"] = {
                "url": self.get_image(self._thumbnail.value)
            }

        # Large image url
        if self._image.value != "":
            self.builder.changes["image"] = {"url": self.get_image(self._image.value)}

        await self.builder.update()
        return await interaction.response.defer()


class EditLinks(discord.ui.Modal):
    _authorurl = OptionalTextInput(
        label="Author url",
        placeholder="Leave empty for none",
    )
    _titleurl = OptionalTextInput(
        label="Title url",
        placeholder="Leave empty for none",
    )

    def __init__(self, builder: "EmbedBuilder") -> None:
        super().__init__(title="Edit links", custom_id="embedbuilder:links")
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Author url
        if self._authorurl.value != "":
            if self.builder.changes.get("author"):
                self.builder.changes["author"]["url"] = self._authorurl.value
            else:
                self.builder.changes["author"] = {"url": self._authorurl.value}

        # Title url
        if self._titleurl.value != "":
            if self.builder.changes.get("title"):
                self.builder.changes["title"]["url"] = self._titleurl.value
            else:
                self.builder.changes["title"] = {"url": self._titleurl.value}

        await self.builder.update()
        return await interaction.response.defer()


class AddField(discord.ui.Modal):
    _fieldname = OptionalTextInput(
        label="Field name",
        placeholder="Leave empty for none",
    )
    _fieldvalue = OptionalTextInput(
        label="Field value",
        placeholder="Leave empty for none",
        style=discord.TextStyle.paragraph,
        max_length=1024,
    )
    _inline = OptionalTextInput(
        label="Inline",
        placeholder="True/False (Default: True)",
        max_length=5,
    )

    def __init__(self, builder: "EmbedBuilder") -> None:
        super().__init__(title="Add field", custom_id="embedbuilder:addfield")
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Add field
        if not self.builder.changes.get("fields"):
            self.builder.changes["fields"] = []

        self.builder.changes["fields"].append(
            {
                "inline": self._inline.value.capitalize() == "True",
                "name": self._fieldname.value or misc.space,
                "value": self._fieldvalue._value or misc.space,
            }
        )

        await self.builder.update()
        return await interaction.response.defer()


class EditColor(discord.ui.Modal):
    _color = OptionalTextInput(
        label="Color",
        placeholder="Leave empty for none (Supports HEX, RGB and Discord colors)",
        max_length=32,
    )

    def __init__(self, builder: "EmbedBuilder") -> None:
        super().__init__(title="Add field", custom_id="embedbuilder:color")
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Edit color
        if self._color.value != "":
            matched = HEX_REGEX.match(self._color.value) or RGB_REGEX.match(
                self._color.value
            )
            try:
                if matched:
                    color = discord.Color.from_str(matched.string)
                else:
                    color: discord.Color = getattr(
                        discord.Color, self._color.value.casefold().replace(" ", "_")
                    )()
                self.builder.changes["color"] = color.value
            except:
                return await interaction.response.send_message(
                    "Unknown color", ephemeral=True
                )

        await self.builder.update()
        return await interaction.response.defer()


class EmbedBuilder(subclasses.View):
    def __init__(
        self,
        embed: discord.Embed,
        bot: "AceBot",
        author: discord.abc.User,
        imported: bool = False,
    ):
        super().__init__()
        self.embed = embed
        self.bot = bot
        self.author = author
        self.message: discord.Message = None
        self.changes = {} if not imported else embed.to_dict()

        self._update_fields()

    def _update_fields(self):
        # Update field count
        count = len(self.changes["fields"]) if self.changes.get("fields") else 0
        self.addfield.disabled = count == 25
        self.removefield.disabled = count == 0
        self.fieldcount.label = f"{count}/25"

    async def update(self):
        # Update embed
        self.embed = self.embed.to_dict()
        self.embed.update(**self.changes)
        self.embed = discord.Embed.from_dict(self.embed)

        self._update_fields()

        return await self.message.edit(embed=self.embed, view=self)

    async def start(self, ctx: commands.Context):
        self.message = await ctx.reply(
            embed=self.embed, view=self, mention_author=False
        )
        return
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        raise errors.NotYourButton
        

    @discord.ui.button(label="Edit :", disabled=True)
    async def embedlabel(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        pass

    @discord.ui.button(label="Text")
    async def edittext(self, interaction: discord.Interaction, button: discord.Button):
        return await interaction.response.send_modal(EditText(builder=self))

    @discord.ui.button(label="Images")
    async def editimages(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        return await interaction.response.send_modal(EditImages(builder=self))

    @discord.ui.button(label="URLs")
    async def editlinks(self, interaction: discord.Interaction, button: discord.Button):
        return await interaction.response.send_modal(EditLinks(builder=self))

    @discord.ui.button(label="Fields :", disabled=True, row=2)
    async def fieldslabel(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        pass

    @discord.ui.button(
        emoji="\N{HEAVY PLUS SIGN}", style=discord.ButtonStyle.green, row=2
    )
    async def addfield(self, interaction: discord.Interaction, button: discord.Button):
        return await interaction.response.send_modal(AddField(builder=self))

    @discord.ui.button(
        emoji="\N{HEAVY MINUS SIGN}",
        style=discord.ButtonStyle.red,
        disabled=True,
        row=2,
    )
    async def removefield(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        self.changes["fields"].pop()
        await self.update()
        return await interaction.response.defer()

    @discord.ui.button(label="0/25", disabled=True, row=2)
    async def fieldcount(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        pass

    @discord.ui.button(label="Export", row=3)
    async def export(self, interaction: discord.Interaction, button: discord.Button):
        _json = json.dumps(self.changes, indent=4)
        content = f"```json\n{_json}```"

        if len(content) <= 2000:
            await interaction.response.send_message(content=content, ephemeral=True)
        else:
            buff = StringIO(_json)
            await interaction.response.send_message(
                content="Output too large to send. Here's an output File",
                file=discord.File(buff, "output.json"),
                ephemeral=True,
            )

    @discord.ui.button(label="Save", style=discord.ButtonStyle.green, row=3)
    async def save(self, interaction: discord.Interaction, button: discord.Button):
        if self.changes != {}:
            embed = discord.Embed.from_dict(self.changes)
            return await interaction.response.edit_message(embed=embed, view=None)
        return await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red, row=3)
    async def delete(self, interaction: discord.Interaction, button: discord.Button):
        return await interaction.message.delete()

    @discord.ui.button(label="Color", row=3)
    async def editcolor(self, interaction: discord.Interaction, button: discord.Button):
        return await interaction.response.send_modal(EditColor(builder=self))
