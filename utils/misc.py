import datetime
import re
from discord.ext import commands
import inspect, os
from typing import Union

class Time(commands.Converter):      
    async def convert(self, ctx: commands.Context, argument: str) -> datetime.datetime:
        # Fixed date like 2024-02-16
        if re.fullmatch("\d{4}-\d{2}-\d{2}", argument):
            return datetime.datetime.strptime(argument, "%Y-%m-%d")

        # Relative date like 1d
        if re.fullmatch("-?\d+d", argument):
            days = int(re.match("-?\d+", argument).group())

            if days > 0:
                return datetime.datetime.today() + datetime.timedelta(days=abs(days))
            else:
                return datetime.datetime.today() - datetime.timedelta(days=abs(days))

def git_source(bot: commands.Bot, obj: Union[commands.Command, commands.Cog, str]=None):
    source_url = 'https://github.com/Aceroph/ace-of-spades'

    if type(obj) is str:
        if obj is None:
            return source_url

        if obj == 'help':
            src = type(bot.help_command)
        else:
            obj = bot.get_command(obj.lower()) or bot.get_cog(obj.capitalize())

    src = obj.callback.__code__ if isinstance(obj, commands.Command) else obj.__class__
    
    filename = inspect.getsourcefile(src)
    lines, firstlineno = inspect.getsourcelines(src)
    location = os.path.relpath(filename).replace('\\', '/')

    return f'{source_url}/blob/master/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}'
