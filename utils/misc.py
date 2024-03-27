from discord.ext import commands
from typing import Optional
import datetime
import inspect
import discord
import re
import os

# Emojis
yes = "<:yes:1221652590153171045>"
no = "<:no:1221652589112721458>"
members = "<:members:1221344536714809385>"
server = "<:server:1221346764574031922>"
delete = "<:delete:1221344534760525824>"
curve = "<:curve:1210049217280745502>"
space = "<:space:1210019090920382464>"
tilde = "<:Tilde:1210003514479083581>"
info = "<:info:1221344535754313758>"
dev = "<:dev:1221284499321651210>"

# Images
python = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png"
github = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"


class Categories:
    presets = {
        "Admin": discord.Permissions._from_value(8),
        "Manager": discord.Permissions._from_value(27812569527),
        "Moderator": discord.Permissions._from_value(17612022151),
    }

    @classmethod
    def categories(cls):
        return [
            "General permissions",
            "Membership permissions",
            "Text channel permissions",
            "Voice channel permissions",
            "Advanced permissions",
        ]

    @classmethod
    def sort(cls, perms: discord.Permissions, category: str):
        c = getattr(discord.Permissions, category.split()[0].lower())
        cperms = [p[0] for p in [*c()] if p[1]]
        return sorted(
            [p for p in perms if p[0] in cperms], key=lambda p: p[1], reverse=True
        )

    @classmethod
    def get_preset(cls, perms: discord.Permissions) -> str:
        for preset, permissions in cls.presets.items():
            if all(
                [
                    perm in [*permissions]
                    for i, perm in enumerate(perms)
                    if [*permissions][i][1]
                ]
            ):
                return preset
        return "Default"


class Time(commands.Converter):
    def __init__(self, return_type: str = "datetime") -> None:
        super().__init__()
        self.return_type = return_type

    async def convert(
        self, ctx: Optional[commands.Context], argument: str
    ) -> datetime.datetime:
        # Fixed date like 2024-02-16
        if re.fullmatch("\\d{4}-\\d{2}-\\d{2}", argument):
            date = datetime.datetime.strptime(argument, "%Y-%m-%d")
            return date if self.return_type == "datetime" else date.date()

        # Relative date like 1d
        if re.fullmatch("-?\\d+d", argument):
            days = int(re.match("-?\\d+", argument).group())

            if days > 0:
                date = datetime.datetime.today() + datetime.timedelta(days=abs(days))
            else:
                date = datetime.datetime.today() - datetime.timedelta(days=abs(days))
            return date if self.return_type == "datetime" else date.date()


def git_source(bot: commands.Bot, obj: str = None):
    source_url = "https://github.com/Aceroph/ace-of-spades"

    if obj is None:
        return source_url

    obj = bot.get_command(obj.lower()) or bot.get_cog(obj.capitalize())

    try:
        src = (
            obj.callback.__code__
            if isinstance(obj, commands.Command)
            else obj.__class__
        )
        filename = inspect.getsourcefile(src)
        lines, firstlineno = inspect.getsourcelines(src)
        location = os.path.relpath(filename).replace("\\", "/")

        return f"{source_url}/blob/master/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}"
    except:
        pass


def time_format(time: int) -> str:
    minutes, seconds = divmod(int(time), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)
    clean = f" {weeks}w {days}d {hours}h {minutes}m {seconds}s"
    for _ in range(clean.count(" 0")):
        index = clean.index(" 0")
        clean = clean[: index + 1] + clean[index + 4 :]
    return clean.strip() or "0s"


def clean_traceback(t: str) -> str:
    for r in re.finditer(re.escape(os.getcwd()), t, flags=re.IGNORECASE):
        t = t.replace(r.group(), f"~{os.sep}ace-of-spades")
    return t


def clean_codeblock(codeblock: str, ctx: commands.Context = None) -> str:
    clean: str = None
    # Get rid of the prefix and command name
    if ctx:
        clean = codeblock.lstrip(ctx.prefix + ctx.command.qualified_name).strip()

    # Remove those ```
    if codeblock.startswith("```") and codeblock.endswith("```"):
        clean = "\n".join(clean.split("\n")[1:-1])

    return clean or codeblock
