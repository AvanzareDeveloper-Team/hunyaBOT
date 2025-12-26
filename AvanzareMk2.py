# AvanzareMk2.py
import os
import discord
from discord.ext import commands
from bot.cogs import auth  # bot/cogs/auth.py の AuthCog
from bot.config import BOT_TOKEN

# ===============================
# Bot 作成
# ===============================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = os.environ.get("TEST_GUILD_ID")  # ギルド同期用（任意）

# ===============================
# on_ready
# ===============================
@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user}")

    # Cog ロード
    try:
        await bot.load_extension("bot.cogs.auth")
        print("[Bot] AuthCog ロード完了")
    except Exception as e:
        print(f"[Bot] Cog ロード失敗: {e}")

    # コマンド同期
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            await bot.tree.sync(guild=guild)
            print(f"[Bot] ギルド {GUILD_ID} にコマンド同期完了")
        else:
            await bot.tree.sync()
            print("[Bot] グローバルコマンド同期完了")
    except Exception as e:
        print(f"[Bot] コマンド同期失敗: {e}")

# ===============================
# 起動
# ===============================
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN が設定されていません")
    bot.run(BOT_TOKEN)
