from main import AceBot
from jishaku.cog import STANDARD_FEATURES
from utils import subclasses

class Jishaku(*STANDARD_FEATURES, subclasses.Cog):
    pass

async def setup(bot: AceBot):
    await bot.add_cog(Jishaku(bot=bot))