import threading
import os
import discord
from discord.ext import commands
from flask import Flask, request
from VersaLog import *

from bot.config import BOT_TOKEN

logger = VersaLog(enum="detailed")

# -----------------
# Flask
# -----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/auth")
def auth():
    code = request.args.get("code")
    if not code:
        return "Error: 認証コードが無効です"
    return f"/verifyで認証してください。認証コードは {code} です。"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# -----------------
# Discord Bot
# -----------------
class Main(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for f in os.listdir("bot/cogs"):
            if f.endswith(".py"):
                await self.load_extension(f"bot.cogs.{f[:-3]}")

    async def on_ready(self):
        await self.tree.sync()
        logger.info(f"Login: {self.user}")

# -----------------
# Entry point
# -----------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot = Main()
    bot.run(BOT_TOKEN)
