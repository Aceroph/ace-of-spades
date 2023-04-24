from discord.ext import commands
import discord
import os
from dotenv import load_dotenv

load_dotenv('.env')

def prefix(bot: commands.Bot, msg):
    client_id = bot.user.id
    return ['a.', f'<@!{client_id}>', f'<@{client_id}>']


class AceHelp(commands.HelpCommand):

    async def send_bot_help(self, mapping):
        filtered = await self.filter_commands(self.context.bot.commands, sort=True)
        names = [command.name for command in filtered]
        available_commands = "\n".join(names)
        embed = discord.Embed(description=available_commands)
        await self.context.send(embed=embed)

    async def send_error_message(self, error):
        await self.get_destination().send(error)


class AceBot(commands.Bot):

    def __init__(self):
        super().__init__(command_prefix=prefix, intents=discord.Intents.all(), help_command=AceHelp())

    async def on_ready(self):
        print(f'Connected as {self.user} (ID: {self.user.id})')


bot = AceBot()
bot.run(os.environ.get('TOKEN'))