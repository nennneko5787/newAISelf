import os

import dotenv
from discord.ext import commands

dotenv.load_dotenv()

bot = commands.Bot(("aicha#", "aicha!", "ai#", "ai!"))


@bot.event
async def setup_hook():
    await bot.load_extension("cogs.aichat")


bot.run(os.getenv("discord"))
