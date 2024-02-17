from jishaku.cog import STANDARD_FEATURES
from utils import subclasses
from main import AceBot

class Jishaku(*STANDARD_FEATURES, subclasses.Cog):
    pass

async def setup(bot: AceBot):
    await bot.add_cog(Jishaku(bot=bot))