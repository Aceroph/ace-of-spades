from discord.ext import commands
from .paginator import Paginator
from discord import Message


async def reply(
    ctx: commands.Context,
    content: str,
    prefix: str = "",
    suffix: str = "",
    *args,
    **kwargs
) -> Message:
    if ctx.interaction and ctx.interaction.response.is_done():
        if len(prefix + content + suffix) > 2000:
            p = Paginator(ctx, prefix=prefix, suffix=suffix, max_lines=100)
            for line in content.split("\n"):
                p.add_line(line)
            return await p.start()

        return await ctx.interaction.followup.send(
            prefix + content + suffix, *args, **kwargs
        )
    else:
        if len(prefix + content + suffix) > 2000:
            p = Paginator(ctx, prefix=prefix, suffix=suffix, max_lines=100)
            for line in content.split("\n"):
                p.add_line(line)
            return await p.start()

        return await ctx.reply(prefix + content + suffix, *args, **kwargs)


commands.Context.reply
