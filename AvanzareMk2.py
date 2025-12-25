import threading
from flask import Flask, request
from pyngrok import ngrok
from discord.ext import commands
from bot.cogs.auth import AuthCog

import os
from bot.config import BOT_TOKEN

# ===============================
# Flask
# ===============================
app = Flask(__name__)
auth_codes_path = "data/auth_codes.json"

try:
    import json
    with open(auth_codes_path, "r", encoding="utf-8") as f:
        auth_codes = json.load(f)
except:
    auth_codes = {}

def save_auth_codes():
    with open(auth_codes_path, "w", encoding="utf-8") as f:
        json.dump(auth_codes, f, indent=2, ensure_ascii=False)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")  # Discord user_id
    if not code or not state:
        return "認証に失敗しました"

    auth_codes[state] = code
    save_auth_codes()
    return "✅ 認証完了しました。Discordに戻ってください。"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ===============================
# ngrok
# ===============================
PORT = int(os.environ.get("PORT", 10000))
public_url = ngrok.connect(PORT, "http")
print(f"ngrok URL: {public_url}")
print(f"Discord アプリのリダイレクト URI に設定してください: {public_url}/callback")

# ===============================
# Discord Bot
# ===============================
bot = commands.Bot(command_prefix="!")

threading.Thread(target=run_flask, daemon=True).start()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.add_cog(AuthCog(bot, public_url))

bot.run(BOT_TOKEN)
