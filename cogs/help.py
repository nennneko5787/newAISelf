import discord
from discord.ext import commands

from datas import messages


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx: commands.Context):
        prefixs = ", ".join(self.bot.command_prefix)
        for p in self.bot.command_prefix:
            if ctx.message.content.startswith(p):
                prefix = p
                break

        await ctx.reply(messages.HELP.format(prefixs=prefixs, prefix=prefix))


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
