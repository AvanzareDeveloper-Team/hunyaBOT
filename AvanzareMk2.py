import threading
import os
import discord
from discord.ext import commands
from flask import Flask, request

from bot.config import BOT_TOKEN
from bot.cogs.auth import AuthCog

# ===============================
# Flask（OAuth callback用）
# ===============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return "❌ 認証に失敗しました"

    try:
        user_id, guild_id = map(int, state.split(":"))
    except ValueError:
        return "❌ state が不正です"

    auth_cog = bot.get_cog("AuthCog")
    if auth_cog:
        # Flask → Discord（非同期）へ処理を渡す
        bot.loop.create_task(
            auth_cog.handle_oauth(code, user_id, guild_id)
        )

    return "✅ 認証完了しました。Discordに戻ってください。"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )

# ===============================
# Discord Bot
# ===============================
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# Flaskを別スレッドで起動
threading.Thread(target=run_flask, daemon=True).start()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    # Cog登録（引数は bot だけ）
    await bot.add_cog(AuthCog(bot))

    await bot.tree.sync()
    print("✅ Commands synced")

# ===============================
# 起動
# ===============================
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN が設定されていません")

    bot.run(BOT_TOKEN)
