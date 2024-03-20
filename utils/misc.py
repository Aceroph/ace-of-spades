from discord.ext import commands
from typing import Optional
import datetime
import inspect
import discord
import re
import os

# Emojis
tilde = '<:Tilde:1210003514479083581>'
curve = '<:curve:1210049217280745502>'
space = '<:space:1210019090920382464>'


class Categories:
    presets = {'Admin': discord.Permissions._from_value(8),
               'Manager': discord.Permissions._from_value(27812569527),
               'Moderator': discord.Permissions._from_value(17612022151)}


    @classmethod
    def categories(cls):
        return ['General permissions', 'Membership permissions', 'Text channel permissions', 'Voice channel permissions', 'Advanced permissions']


    @classmethod
    def sort(cls, perms: discord.Permissions, category: str):
        c = getattr(discord.Permissions, category.split()[0].lower())
        cperms = [p[0] for p in [*c()] if p[1]]
        return sorted([p for p in perms if p[0] in cperms], key=lambda p: p[1], reverse=True)


    @classmethod
    def get_preset(cls, perms: discord.Permissions) -> str:
        for preset, permissions in cls.presets.items():
            if all([perm in [*permissions] for i, perm in enumerate(perms) if [*permissions][i][1]]):
                return preset
        return 'Default'
        

class Time(commands.Converter):
    def __init__(self, return_type: str='datetime') -> None:
        super().__init__()
        self.return_type = return_type


    async def convert(self, ctx: Optional[commands.Context], argument: str) -> datetime.datetime:
        # Fixed date like 2024-02-16
        if re.fullmatch("\\d{4}-\\d{2}-\\d{2}", argument):
            date = datetime.datetime.strptime(argument, "%Y-%m-%d")
            return date if self.return_type == 'datetime' else date.date()

        # Relative date like 1d
        if re.fullmatch("-?\\d+d", argument):
            days = int(re.match("-?\\d+", argument).group())

            if days > 0:
                date = datetime.datetime.today() + datetime.timedelta(days=abs(days))
            else:
                date = datetime.datetime.today() - datetime.timedelta(days=abs(days))
            return date if self.return_type == 'datetime' else date.date()


def git_source(bot: commands.Bot, obj: str=None):
    source_url = 'https://github.com/Aceroph/ace-of-spades'
    
    if obj is None:
        return source_url
    
    if obj == 'help':
        obj = bot.help_command
    else:
        obj = bot.get_command(obj.lower()) or bot.get_cog(obj.capitalize())

    try:
        src = obj.callback.__code__ if isinstance(obj, commands.Command) else obj.__class__
    except:
        return
    
    filename = inspect.getsourcefile(src)
    lines, firstlineno = inspect.getsourcelines(src)
    location = os.path.relpath(filename).replace('\\', '/')

    return f'{source_url}/blob/master/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}'


def clean_traceback(t: str) -> str:
    for r in re.finditer(re.escape(os.getcwd()), t, flags=re.IGNORECASE):
        t = t.replace(r.group(), f'~{os.sep}ace-of-spades')
    return t
