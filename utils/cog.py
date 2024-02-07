from discord.ext import commands
import time

class Cog(commands.Cog):
    def __init__(self):
        self.emoji: str = "<:sadcowboy:1002608868360208565>"
        self.time: float = time.time()
        self.cmds = 0
    
    @commands.Cog.listener()
    async def on_command_completion(self, command: commands.Command):
        command.cog.cmds += 1 if issubclass(type(command.cog), type(self)) else 0