import threading
import discord
from discord.ext import commands
from flask import Flask, request
from VersaLog import *

from bot.config import BOT_TOKEN

logger = VersaLog(enum="detailed")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/auth")
def auth():
    code = request.args.get("code")
    if not code: return "Error: 認証コードが無効です"
    return f"/verifyで認証してください。認証コードは{code}です。"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

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
        logger.info(f"Login: {self.user}")

# # Cogs 読み込み
# COGS = [
#     "bot.cogs.invite_watch",
#     "bot.cogs.auth",
#     "bot.cogs.ticket",
#     "bot.cogs.role_panel",
#     "bot.cogs.global_chat",
#     "bot.cogs.help",
# ]

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot = Main()
    bot.run(BOT_TOKEN)
