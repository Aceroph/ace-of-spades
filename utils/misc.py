from typing import cast, Iterable
from discord.ext import commands
from cogs import EXTENSIONS
from . import subclasses
import unicodedata
import difflib
import requests
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
blueline = "<:blueline:1224902075226390638>"
whiteline = "<:whiteline:1224902073980682272>"

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


class Module(commands.Converter):
    async def convert(self, ctx: commands.Context, module: str):
        """Converts given module query to Cog"""
        mod = None
        for extension in EXTENSIONS:
            r = difflib.SequenceMatcher(
                None, extension.split(".")[-1], module.split(".")[-1]
            ).ratio()
            if r >= 0.60:
                mod: subclasses.Cog = extension
                break

        if not mod:
            raise commands.errors.ExtensionNotFound

        for name, cog in ctx.bot.cogs.items():
            if name.casefold() == mod.split(".")[-1]:
                return cast(subclasses.Cog, cog)

        return mod


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
    clean = re.match(r"`{3}[a-zA-Z]*[ \n](.*)\n?`{3}", codeblock, flags=re.S)
    if clean:
        return clean.group(1)

    return codeblock


def avg(x: Iterable[float | int]) -> float | int:
    return sum(x) / len(x)


def clean_string(string: str) -> str:
    return unicodedata.normalize("NFD", string.casefold().replace(",", "")).encode(
        "ASCII", "ignore"
    )


runtimes: list[dict] = requests.get("https://emkc.org/api/v2/piston/runtimes").json()
literal_runtimes = set()
for r in runtimes:
    literal_runtimes.add(r["language"])
    for alias in r["aliases"]:
        literal_runtimes.add(alias)
