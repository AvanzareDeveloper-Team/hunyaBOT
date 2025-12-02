# pyright: reportMissingImports=false
"""
フニャBOT（グローバルチャット + 経済 + ロール購入 + Flask）
要: python 3.13+, discord.py 2.6+, pillow
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from datetime import timezone

# Flask（Renderなどで常時起動用）
from flask import Flask
app = Flask("フニャBOT")
@app.route("/")
def home():
    return "フニャBOT稼働中！"

# Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None

# ----------------------------
# INTENTS & BOT
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# データファイル
# ----------------------------
DATA_FILE = "data.json"    # グローバルチャット
ECON_FILE = "economy.json" # 経済ポイント

# ----------------------------
# データ読み込み・保存
# ----------------------------
def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)

data = load_json(DATA_FILE, {"global_channels": {}, "global_mute": {}, "global_ban": []})
economy = load_json(ECON_FILE, {"balances": {}, "daily_count": {}, "shop": {}})

def save_all():
    save_json(DATA_FILE, data)
    save_json(ECON_FILE, economy)

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
            if getattr(e, "status", None) == 429:
                await asyncio.sleep(getattr(e, "retry_after", 1))
            elif getattr(e, "status", None) == 404:
                return None
            else:
                raise

# ----------------------------
# グローバルチャット送信
# ----------------------------
async def broadcast_global(channel, author, content, attachments):
    guild_id = str(channel.guild.id)
    for name, ch_list in data.get("global_channels", {}).items():
        if f"{guild_id}:{channel.id}" in ch_list:
            for target in list(ch_list):
                tgt_guild_id, tgt_ch_id = map(int, target.split(":"))
                if tgt_guild_id == channel.guild.id and tgt_ch_id == channel.id:
                    continue
                tgt_guild = bot.get_guild(tgt_guild_id)
                if not tgt_guild:
                    continue
                tgt_channel = tgt_guild.get_channel(tgt_ch_id)
                if not tgt_channel:
                    continue
                if str(author.id) in data.get("global_ban", []):
                    continue
                if name in data.get("global_mute", {}) and str(author.id) in data["global_mute"][name]:
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
# メッセージイベント
# ----------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # グローバルチャット
    await broadcast_global(message.channel, message.author, message.content, message.attachments)

    # 経済ポイント (3メッセージで1ポイント)
    user_id = str(message.author.id)
    today = message.created_at.date().isoformat()
    economy["daily_count"].setdefault(user_id, {})
    economy["daily_count"][user_id][today] = economy["daily_count"][user_id].get(today, 0) + 1
    if economy["daily_count"][user_id][today] % 3 == 0:
        economy["balances"][user_id] = economy["balances"].get(user_id, 0) + 1
        save_json(ECON_FILE, economy)

    await bot.process_commands(message)

# ----------------------------
# 経済コマンド
# ----------------------------
@bot.tree.command(name="balance", description="自分のふにゃを確認")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    points = economy.get("balances", {}).get(user_id, 0)
    await interaction.response.send_message(f"あなたのふにゃ: {points}")

@bot.tree.command(name="top_points", description="ふにゃランキング（上位10）")
async def top_points(interaction: discord.Interaction):
    top10 = sorted(economy.get("balances", {}).items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 ふにゃランキング（上位10）", color=discord.Color.gold())
    for i, (uid, pts) in enumerate(top10, 1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"ユーザーID:{uid}"
        embed.add_field(name=f"{i}. {name}", value=f"{pts} ふにゃ", inline=False)
    await interaction.response.send_message(embed=embed)

# ----------------------------
# ロール購入コマンド
# ----------------------------
@bot.tree.command(name="buy_role", description="管理者: このロールをふにゃで購入可能にする")
@app_commands.describe(role="販売するロール", price="価格（ポイント）")
async def buy_role(interaction: discord.Interaction, role: discord.Role, price: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者専用です", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    economy["shop"].setdefault(guild_id, {})[str(role.id)] = price
    save_json(ECON_FILE, economy)
    await interaction.response.send_message(f"{role.name} を {price} ふにゃで購入可能にしました", ephemeral=True)

@bot.tree.command(name="buyrole", description="ロールを購入します")
@app_commands.describe(role="購入したいロール")
async def buyrole_cmd(interaction: discord.Interaction, role: discord.Role):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    cost = economy.get("shop", {}).get(guild_id, {}).get(str(role.id))
    if cost is None:
        await interaction.response.send_message("このロールは購入不可です", ephemeral=True)
        return
    balance = economy.get("balances", {}).get(user_id, 0)
    if balance < cost:
        await interaction.response.send_message(f"フニャが足りません！ 必要: {cost}、所持: {balance}", ephemeral=True)
        return
    economy["balances"][user_id] -= cost
    save_json(ECON_FILE, economy)
    await interaction.user.add_roles(role)
    await interaction.response.send_message(f"{role.name} を購入しました！ 残りフニャ: {economy['balances'][user_id]}")

# ----------------------------
# グローバルチャットコマンド
# ----------------------------
@bot.tree.command(name="global_create", description="グローバルチャットを作成")
@app_commands.describe(name="グローバルチャット名")
async def global_create(interaction: discord.Interaction, name: str):
    if name in data.get("global_channels", {}):
        await interaction.response.send_message("既に存在します", ephemeral=True)
        return
    data["global_channels"][name] = []
    save_json(DATA_FILE, data)
    await interaction.response.send_message(f"グローバルチャット `{name}` 作成", ephemeral=True)

@bot.tree.command(name="global_join", description="このチャンネルをグローバルチャットに参加")
@app_commands.describe(name="グローバルチャット名")
async def global_join(interaction: discord.Interaction, name: str):
    ch = interaction.channel
    gid = str(ch.guild.id)
    identifier = f"{gid}:{ch.id}"
    if name not in data.get("global_channels", {}):
        await interaction.response.send_message("存在しないグローバルチャットです", ephemeral=True)
        return
    if identifier in data["global_channels"][name]:
        await interaction.response.send_message("すでに参加済みです", ephemeral=True)
        return
    data["global_channels"][name].append(identifier)
    save_json(DATA_FILE, data)
    await interaction.response.send_message(f"このチャンネルを `{name}` に参加させました", ephemeral=True)

@bot.tree.command(name="global_leave", description="グローバルチャットから退出")
@app_commands.describe(name="グローバルチャット名")
async def global_leave(interaction: discord.Interaction, name: str):
    ch = interaction.channel
    gid = str(ch.guild.id)
    identifier = f"{gid}:{ch.id}"
    if name not in data.get("global_channels", {}) or identifier not in data["global_channels"][name]:
        await interaction.response.send_message("参加していません", ephemeral=True)
        return
    data["global_channels"][name].remove(identifier)
    save_json(DATA_FILE, data)
    await interaction.response.send_message(f"このチャンネルを `{name}` から退出しました", ephemeral=True)

# ----------------------------
# 起動
# ----------------------------
@bot.event
async def on_ready():
    print(f"ログイン成功: {bot.user}")
    try:
        await bot.tree.sync()
        print("スラッシュコマンド同期完了")
    except Exception as e:
        print(f"同期エラー: {e}")

TOKEN = os.environ.get("DISCORD_TOKEN")
assert TOKEN, "DISCORD_TOKEN が設定されていません"
bot.run(TOKEN)
