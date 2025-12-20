import threading
import discord
from discord.ext import commands
from bot.web import app
from bot.config import BOT_TOKEN

class Main(commands.Bot):
    def __init__(self):
        Intents = discord.Intents.default()
        Intents.members = True
        Intents.message_content = True
        super().__init__(command_prefix="!", intents=Intents)

    async def setup_hook(self):
        import os
        for f in os.listdir("bot/cogs"):
            if f.endswith(".py"):
                await self.load_extension(f"bot.cogs.{f[:-3]}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.tree.sync()
        print(f"Login: {self.user}")


def run_flask():
    app.run(host="0.0.0.0")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot = Main()
    bot.run(BOT_TOKEN)
