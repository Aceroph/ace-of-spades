from main import AceBot
from jishaku.cog import STANDARD_FEATURES
import utils

class Jishaku(*STANDARD_FEATURES, utils.Cog):
    pass

async def setup(bot: AceBot):
    await bot.add_cog(Jishaku(bot=bot))