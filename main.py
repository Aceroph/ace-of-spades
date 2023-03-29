import discord

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$ping'):
        await message.channel.send('pong!')

client.run('OTE5MDUyNjQ3NjA3MTkzNjIw.G9sXxl.BOlXaIe3UJ_-62hmREqQxCCPTOXQOY2JIZaAkU')