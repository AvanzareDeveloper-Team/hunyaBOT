import re
import discord
from discord.ext import commands

INVITE = re.compile(r"(discord\.gg|discord\.com/invite)/\S+")
URL = re.compile(r"https?://\S+")

class InviteWatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cfg = {}

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.guild:
            return

        g = self.cfg.setdefault(msg.guild.id, {"invite": False, "url": False})
        if g["invite"] and INVITE.search(msg.content):
            await msg.delete()
        elif g["url"] and URL.search(msg.content):
            await msg.delete()

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def invite_watch(self, ctx, on: bool):
        self.cfg.setdefault(ctx.guild.id, {})["invite"] = on
        await ctx.reply("招待リンク監視設定変更")

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def url_watch(self, ctx, on: bool):
        self.cfg.setdefault(ctx.guild.id, {})["url"] = on
        await ctx.reply("URL監視設定変更")

async def setup(bot):
    await bot.add_cog(InviteWatch(bot))
