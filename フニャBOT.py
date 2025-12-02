# pyright: reportMissingImports=false
"""
完全統合版フニャBOT（グローバルチャット + 経済 + ロール購入 + Flask監視）
要: python, discord.py v2.x, pillow, Flask
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
from datetime import datetime, timezone

# Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

# Flask
from flask import Flask

# ----------------------------
# INTENTS & BOT
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# Flask Webサーバー
# ----------------------------
app = Flask("フニャBOT")

@app.route("/")
def home():
    return "フニャBOT 稼働中！"

# ----------------------------
# ファイル定義
# ----------------------------
DATA_FILE = "global_chat_data.json"
ECONOMY_FILE = "economy_data.json"

# ----------------------------
# アプリデータ
# ----------------------------
data = {"global_channels": {}, "global_mute": {}, "global_ban": []}
economy_data = {}

# ----------------------------
# ファイル入出力
# ----------------------------
def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_app_data(): save_json(DATA_FILE, data)
def load_app_data(): global data; data = load_json(DATA_FILE, data)
def save_economy(): save_json(ECONOMY_FILE, economy_data)
def load_economy(): global economy_data; economy_data = load_json(ECONOMY_FILE, economy_data)

# 初期ロード
load_app_data()
load_economy()

# ----------------------------
# safe_call
# ----------------------------
async def safe_call(coro, delay: float = 0.2):
    while True:
        try:
            res = await coro
            await asyncio.sleep(delay)
            return res
        except discord.HTTPException as e:
            status = getattr(e, "status", None)
            if status == 429:
                retry = getattr(e, "retry_after", 1)
                await asyncio.sleep(retry)
            elif status == 404:
                return None
            else:
                raise

# ----------------------------
# チャンネル判定
# ----------------------------
def is_text_sendable(ch):
    return isinstance(ch, (discord.TextChannel, discord.Thread))

# ----------------------------
# グローバルチャット転送
# ----------------------------
async def broadcast_global_message(channel, author, content, attachments):
    try:
        guild_id = str(channel.guild.id)
    except Exception:
        return

    for g_name, ch_list in data.get("global_channels", {}).items():
        if f"{guild_id}:{channel.id}" in ch_list:
            for target in list(ch_list):
                try:
                    tgt_guild_id, tgt_ch_id = map(int, target.split(":"))
                except Exception:
                    continue
                if tgt_guild_id == channel.guild.id and tgt_ch_id == channel.id:
                    continue
                tgt_guild = bot.get_guild(tgt_guild_id)
                if not tgt_guild:
                    continue
                tgt_channel = tgt_guild.get_channel(tgt_ch_id)
                if not tgt_channel or not is_text_sendable(tgt_channel):
                    continue
                if str(author.id) in data.get("global_ban", []):
                    continue
                if g_name in data.get("global_mute", {}) and str(author.id) in data["global_mute"].get(g_name, []):
                    continue
                try:
                    embed = discord.Embed(description=content or "(添付のみ)", color=discord.Color.blue())
                    embed.set_author(name=f"{author.display_name}@{channel.guild.name}", icon_url=author.display_avatar.url)
                    for a in attachments:
                        if a.content_type and a.content_type.startswith("image"):
                            embed.set_image(url=a.url)
                    await safe_call(tgt_channel.send(embed=embed))
                except Exception:
                    continue

# ----------------------------
# メッセージ処理
# ----------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # グローバルチャット
    await broadcast_global_message(message.channel, message.author, message.content, message.attachments)

    # 経済ポイント (3メッセージに1回)
    if message.guild:
        user_id = str(message.author.id)
        today = message.created_at.date().isoformat()
        economy_data.setdefault("daily_message_count", {}).setdefault(user_id, {})
        count_today = economy_data["daily_message_count"][user_id].get(today, 0) + 1
        economy_data["daily_message_count"][user_id][today] = count_today

        if count_today % 3 == 0:
            economy_data.setdefault("balances", {})
            economy_data["balances"][user_id] = economy_data["balances"].get(user_id, 0) + 1
            save_economy()

    await bot.process_commands(message)

# ----------------------------
# 経済コマンド
# ----------------------------
@bot.tree.command(name="balance", description="自分のふにゃを確認")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    points = economy_data.get("balances", {}).get(user_id, 0)
    await interaction.response.send_message(f"あなたのふにゃ: {points}")

# ロール購入
@bot.tree.command(name="buy_role", description="管理者: このロールをふにゃで購入可能にする")
@app_commands.describe(role="販売するロール", price="価格（ポイント）")
async def buy_role(interaction: discord.Interaction, role: discord.Role, price: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者専用コマンドです", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    economy_data.setdefault("shop", {}).setdefault(guild_id, {})[str(role.id)] = price
    save_economy()
    await interaction.response.send_message(f"{role.name} を {price} ふにゃで購入可能にしました", ephemeral=True)

@bot.tree.command(name="buyrole", description="ロールを購入します")
@app_commands.describe(role="購入したいロール", cost="必要なフニャ数")
async def buyrole_cmd(interaction: discord.Interaction, role: discord.Role, cost: int):
    user_id = str(interaction.user.id)
    balance = economy_data.setdefault("balances", {}).get(user_id, 0)

    if balance < cost:
        await interaction.response.send_message(f"フニャが足りません！ 必要: {cost}、所持: {balance}", ephemeral=True)
        return

    economy_data["balances"][user_id] = balance - cost
    save_economy()

    try:
        await interaction.user.add_roles(role)
    except Exception as e:
        await interaction.response.send_message(f"ロール付与エラー: {e}", ephemeral=True)
        return

    await interaction.response.send_message(f"{role.name} を購入しました！\n残りフニャ: {economy_data['balances'][user_id]}")

# ----------------------------
# グローバルチャットコマンド
# ----------------------------
@bot.tree.command(name="global_create", description="グローバルチャットを作成")
@app_commands.describe(name="グローバルチャット名")
async def global_create(interaction: discord.Interaction, name: str):
    if name in data.get("global_channels", {}):
        await interaction.response.send_message("既に存在します", ephemeral=True)
        return
    data.setdefault("global_channels", {})[name] = []
    save_app_data()
    await interaction.response.send_message(f"グローバルチャット `{name}` 作成", ephemeral=True)

@bot.tree.command(name="global_join", description="このチャンネルをグローバルチャットに参加")
@app_commands.describe(name="グローバルチャット名")
async def global_join(interaction: discord.Interaction, name: str):
    ch = interaction.channel
    identifier = f"{ch.guild.id}:{ch.id}"
    if name not in data.get("global_channels", {}):
        await interaction.response.send_message("存在しないグローバルチャットです", ephemeral=True)
        return
    if identifier in data["global_channels"][name]:
        await interaction.response.send_message("すでに参加済みです", ephemeral=True)
        return
    data["global_channels"][name].append(identifier)
    save_app_data()
    await interaction.response.send_message(f"このチャンネルを `{name}` に参加させました", ephemeral=True)

@bot.tree.command(name="global_leave", description="グローバルチャットから退出")
@app_commands.describe(name="グローバルチャット名")
async def global_leave(interaction: discord.Interaction, name: str):
    ch = interaction.channel
    identifier = f"{ch.guild.id}:{ch.id}"
    if name not in data.get("global_channels", {}) or identifier not in data["global_channels"][name]:
        await interaction.response.send_message("参加していません", ephemeral=True)
        return
    data["global_channels"][name].remove(identifier)
    save_app_data()
    await interaction.response.send_message(f"このチャンネルを `{name}` から退出しました", ephemeral=True)

# ----------------------------
# Bot起動
# ----------------------------
@bot.event
async def on_ready():
    print(f"ログイン成功: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"/コマンド同期完了: {len(synced)} 件")
    except Exception as e:
        print(f"同期エラー: {e}")

# ----------------------------
# 同時起動用
# ----------------------------
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

import threading
threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("DISCORD_TOKEN")
assert TOKEN, "DISCORD_TOKEN が設定されていません"
bot.run(TOKEN)
