from discord.ext import commands

def guild_command(*guilds: int):
    async def predicate(ctx: commands.Context):
        return ctx.guild.id in guilds
    return commands.check(predicate)