from main import AceBot
from jishaku.cog import STANDARD_FEATURES

class Jishaku(*STANDARD_FEATURES):
    pass

async def setup(bot: AceBot):
    cog = Jishaku(bot=bot)
    cog.emoji = "<:sadcowboy:1002608868360208565>"
    await bot.add_cog(cog)