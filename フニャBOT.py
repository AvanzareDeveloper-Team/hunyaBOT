# pyright: reportMissingImports=false
"""
完全統合版フニャBOT（グローバルチャット + ロールパネル + 統計(5分更新, 過去7日グラフ)）
要: python, discord.py v2.x, pillow
Replit: pip install pillow
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import io

# Pillow import (案内付き)
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None



# ----------------------------
# INTENTS & BOT
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# ファイル定義
# ----------------------------
DATA_FILE = "global_chat_data.json"
ROLE_PANEL_FILE = "role_panels.json"
STATS_FILE = "stats_data.json"  # daily_messages, stats_channel_id, last_stats_message

# ----------------------------
# アプリデータ（既存機能）
# ----------------------------
data: Dict[str, Any] = {
    "global_channels": {},
    "global_mute": {},
    "global_ban": []
}
role_panels: Dict[str, Any] = {}

# ----------------------------
# 統計用永続データ構造
# stats_data = {
#   "daily_messages": { "<guild_id>": { "<YYYY-MM-DD>": count, ... }, ... },
#   "stats_channel_id": { "<guild_id>": channel_id, ... },
#   "last_stats_message": { "<guild_id>": message_id, ... }
# }
# ----------------------------
stats_data: Dict[str, Any] = {
    "daily_messages": {},
    "stats_channel_id": {},
    "last_stats_message": {}
}

# ----------------------------
# ファイル入出力
# ----------------------------
def save_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)

def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_app_data():
    save_json(DATA_FILE, data)

def load_app_data():
    global data
    data = load_json(DATA_FILE, data)

def save_role_panels():
    save_json(ROLE_PANEL_FILE, role_panels)

def load_role_panels():
    global role_panels
    role_panels = load_json(ROLE_PANEL_FILE, role_panels)

def save_stats_data():
    save_json(STATS_FILE, stats_data)

def load_stats_data():
    global stats_data
    stats_data = load_json(STATS_FILE, stats_data)
    # Ensure keys exist
    stats_data.setdefault("daily_messages", {})
    stats_data.setdefault("stats_channel_id", {})
    stats_data.setdefault("last_stats_message", {})

# 初期ロード
load_app_data()
load_role_panels()
load_stats_data()

# ----------------------------
# safe_call: 429対応のラッパー
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
# 送信可能チャンネル判定
# （TextChannel と Thread のみに送信する）
# ----------------------------
def is_text_sendable(ch: Optional[discord.abc.GuildChannel]) -> bool:
    return isinstance(ch, (discord.TextChannel, discord.Thread))

# also for fetching/deleting messages: channel must be Messageable (TextChannel or Thread or DM)
def is_messageable(ch) -> bool:
    return isinstance(ch, (discord.abc.Messageable, discord.TextChannel, discord.Thread))

# ----------------------------
# グローバルチャット転送
# ----------------------------
async def broadcast_global_message(channel: discord.abc.GuildChannel, author: discord.Member, content: str, attachments):
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
                # skip own server/channel
                if tgt_guild_id == channel.guild.id and tgt_ch_id == channel.id:
                    continue
                tgt_guild = bot.get_guild(tgt_guild_id)
                if not tgt_guild:
                    continue
                tgt_channel = tgt_guild.get_channel(tgt_ch_id)
                if not tgt_channel:
                    continue
                # ban/mute checks
                if str(author.id) in data.get("global_ban", []):
                    continue
                if g_name in data.get("global_mute", {}) and str(author.id) in data["global_mute"].get(g_name, []):
                    continue
                try:
                    if not is_text_sendable(tgt_channel):
                        continue
                    embed = discord.Embed(description=content or "(添付のみ)", color=discord.Color.blue())
                    embed.set_author(name=f"{author.display_name}@{channel.guild.name}", icon_url=author.display_avatar.url)
                    await safe_call(tgt_channel.send(embed=embed))
                    for a in attachments:
                        # send attachments as URLs (simple)
                        await safe_call(tgt_channel.send(a.url))
                except Exception:
                    continue

# ----------------------------
# メッセージカウント（UTC日付文字列で保存）
# ----------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # グローバルチャット転送
    await broadcast_global_message(message.channel, message.author, message.content, message.attachments)

    # stats: increment for message.created_at in UTC
    if message.guild:
        guild_id_str = str(message.guild.id)
        date_str = message.created_at.astimezone(timezone.utc).date().isoformat()
        stats_data.setdefault("daily_messages", {})
        guild_daily = stats_data["daily_messages"].setdefault(guild_id_str, {})
        guild_daily[date_str] = guild_daily.get(date_str, 0) + 1
        stats_data["daily_messages"][guild_id_str] = guild_daily
        save_stats_data()

    # process commands after handling
    await bot.process_commands(message)

# ----------------------------
# on_ready
# ----------------------------
@bot.event
async def on_ready():
    print(f"{bot.user} 起動")
    # start stats loop (safe)
    try:
        stats_loop.start()
    except RuntimeError:
        pass
    # try sync commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print("Command sync error:", e)

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
    if ch is None or not hasattr(ch, "guild") or ch.guild is None:
        await interaction.response.send_message("このコマンドはサーバーのチャンネルで実行してください", ephemeral=True)
        return
    guild_id = str(ch.guild.id)
    if name not in data.get("global_channels", {}):
        await interaction.response.send_message("存在しないグローバルチャットです", ephemeral=True)
        return
    identifier = f"{guild_id}:{ch.id}"
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
    if ch is None or not hasattr(ch, "guild") or ch.guild is None:
        await interaction.response.send_message("このコマンドはサーバーのチャンネルで実行してください", ephemeral=True)
        return
    guild_id = str(ch.guild.id)
    identifier = f"{guild_id}:{ch.id}"
    if name not in data.get("global_channels", {}) or identifier not in data["global_channels"][name]:
        await interaction.response.send_message("参加していません", ephemeral=True)
        return
    data["global_channels"][name].remove(identifier)
    save_app_data()
    await interaction.response.send_message(f"このチャンネルを `{name}` から退出しました", ephemeral=True)

# ----------------------------
# ロール付与パネル
# ----------------------------
@bot.tree.command(name="create_role_panel", description="任意のロール付与パネルを作成")
@app_commands.describe(
    title="パネルタイトル",
    role1="ロール1",
    role2="ロール2",
    role3="ロール3",
    role4="ロール4",
    role5="ロール5"
)
async def create_role_panel(
    interaction: discord.Interaction,
    title: str,
    role1: Optional[discord.Role] = None,
    role2: Optional[discord.Role] = None,
    role3: Optional[discord.Role] = None,
    role4: Optional[discord.Role] = None,
    role5: Optional[discord.Role] = None
):
    ch = interaction.channel
    if ch is None or not hasattr(ch, "guild") or ch.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内のチャンネルで実行してください", ephemeral=True)
        return

    roles = [r for r in (role1, role2, role3, role4, role5) if r is not None]
    if not roles:
        await interaction.response.send_message("最低1つのロールを指定してください", ephemeral=True)
        return

    if not is_text_sendable(ch):  # safety for Forum/Category/DM
        await interaction.response.send_message("このチャンネルではパネルを作成できません", ephemeral=True)
        return

    embed = discord.Embed(title=title, description="以下のボタンでロールを取得できます", color=discord.Color.green())
    view = discord.ui.View()
    for r in roles:
        button = discord.ui.Button(label=r.name, style=discord.ButtonStyle.primary)
        async def callback(interaction: discord.Interaction, role=r):
            # interaction.user must be a Member
            user = interaction.user
            if not isinstance(user, discord.Member):
                await interaction.response.send_message("メンバー情報が取得できません", ephemeral=True)
                return
            try:
                if role in user.roles:
                    await user.remove_roles(role)
                    await interaction.response.send_message(f"{role.name} を解除しました", ephemeral=True)
                else:
                    await user.add_roles(role)
                    await interaction.response.send_message(f"{role.name} を付与しました", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("権限が不十分でロールを付与/解除できませんでした", ephemeral=True)
        button.callback = callback
        view.add_item(button)

    msg = await ch.send(embed=embed, view=view)
    role_panels[str(msg.id)] = {"title": title, "roles": [r.id for r in roles]}
    save_role_panels()
    await interaction.response.send_message("ロール付与パネルを作成しました", ephemeral=True)

# ----------------------------
# 統計ヘルパー
# ----------------------------
def get_count(guild_id: int, date_obj: datetime.date) -> int:
    return int(stats_data.get("daily_messages", {}).get(str(guild_id), {}).get(date_obj.isoformat(), 0))

def ensure_stats_keys():
    stats_data.setdefault("daily_messages", {})
    stats_data.setdefault("stats_channel_id", {})
    stats_data.setdefault("last_stats_message", {})

async def safe_delete_message(ch: discord.abc.Messageable, message_id: int):
    try:
        # fetch_message exists on TextChannel/Thread/DM (Messageable)
        msg = await ch.fetch_message(message_id)  # type: ignore
        await msg.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException, AttributeError):
        return

def create_7day_graph(guild_id: int):
    # if pillow not available, raise
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow が見つかりません。pip install pillow を実行してください。")

    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
    counts = [get_count(guild_id, d) for d in dates]
    labels = [d.strftime("%m/%d") for d in dates]

    # image settings
    w, h = 700, 320
    margin = 40
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # fonts
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", 18)
        font = ImageFont.truetype("DejaVuSans.ttf", 14)
    except Exception:
        title_font = ImageFont.load_default()
        font = ImageFont.load_default()

    # title
    draw.text((margin, 8), "過去7日間のメッセージ数", fill=(0, 0, 0), font=title_font)

    # chart area
    chart_top = 40
    chart_left = margin
    chart_right = w - margin
    chart_bottom = h - margin
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    max_count = max(counts) if max(counts) > 0 else 1

    # bar sizing
    num = len(counts)
    # spacing and bar width
    total_spacing = chart_w * 0.12
    spacing = int(total_spacing / (num + 1))
    bar_w = int((chart_w - total_spacing) / num)

    x = chart_left + spacing
    for i, val in enumerate(counts):
        # height scale
        bar_h = int((val / max_count) * (chart_h - 40))
        x0 = x
        y0 = chart_bottom - bar_h
        x1 = x + bar_w
        y1 = chart_bottom
        draw.rectangle((x0, y0, x1, y1), fill=(102, 170, 255))
        # label bbox
        bbox = draw.textbbox((0, 0), labels[i], font=font)
        lw = bbox[2] - bbox[0]
        # draw label centered
        draw.text((x0 + (bar_w - lw) / 2, chart_bottom + 6), labels[i], fill=(0, 0, 0), font=font)
        # draw value above bar
        v_bbox = draw.textbbox((0, 0), str(val), font=font)
        vw = v_bbox[2] - v_bbox[0]
        draw.text((x0 + (bar_w - vw) / 2, y0 - 16), str(val), fill=(0, 0, 0), font=font)
        x += bar_w + spacing

    # save to BytesIO
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ----------------------------
# 統計更新（guild 単位）
# ----------------------------
async def update_stats_for_guild(guild_id: int):
    ensure_stats_keys()
    channel_id = stats_data["stats_channel_id"].get(str(guild_id))
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    guild = bot.get_guild(int(guild_id))
    if channel is None or guild is None:
        return
    if not is_text_sendable(channel):
        return

    # delete previous
    last_msg_id = stats_data["last_stats_message"].get(str(guild_id))
    if last_msg_id:
        await safe_delete_message(channel, int(last_msg_id))

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    today_count = get_count(guild_id, today)
    yesterday_count = get_count(guild_id, yesterday)

    online_count = sum(1 for m in guild.members if getattr(m, "status", discord.Status.offline) != discord.Status.offline)
    total_guilds = len(bot.guilds)

    embed = discord.Embed(title="📊 サーバー統計", color=discord.Color.blue())
    embed.add_field(name="📅 今日のメッセージ数", value=str(today_count), inline=False)
    embed.add_field(name="📅 昨日のメッセージ数", value=str(yesterday_count), inline=False)
    embed.add_field(name="🟢 オンライン人数", value=str(online_count), inline=False)
    embed.add_field(name="🌐 BOT参加サーバー数", value=str(total_guilds), inline=False)
    embed.set_footer(text=f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # try to create graph (if pillow missing, embed only)
    try:
        buf = create_7day_graph(guild_id)
        file = discord.File(fp=buf, filename="7days.png")
        embed.set_image(url="attachment://7days.png")
        sent = await channel.send(embed=embed, file=file)
    except RuntimeError as e:
        # pillow missing
        sent = await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        return

    # store last message id
    stats_data["last_stats_message"][str(guild_id)] = sent.id
    save_stats_data()

@bot.tree.command(name="server_stats", description="このチャンネルに統計と過去7日グラフを表示・5分ごとに自動更新")
async def server_stats(interaction: discord.Interaction):
    ch = interaction.channel
    if ch is None or not hasattr(ch, "guild") or ch.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内のチャンネルで実行してください", ephemeral=True)
        return
    if not is_text_sendable(ch):
        await interaction.response.send_message("このチャンネルには統計を表示できません（テキストチャンネルを使ってください）", ephemeral=True)
        return
    guild_id = ch.guild.id
    stats_data.setdefault("stats_channel_id", {})[str(guild_id)] = ch.id
    save_stats_data()
    # immediate update
    await update_stats_for_guild(guild_id)
    await interaction.response.send_message("統計をこのチャンネルに表示・自動更新します（5分ごと）", ephemeral=True)

# ----------------------------
# 定期ループ（5分）
# ----------------------------
@tasks.loop(minutes=5)
async def stats_loop():
    # iterate snapshot of guild ids
    for guild_id_str in list(stats_data.get("stats_channel_id", {}).keys()):
        try:
            await update_stats_for_guild(int(guild_id_str))
        except Exception:
            continue

# ----------------------------
# 起動（TOKEN 必須）
# ----------------------------
TOKEN = os.environ.get("DISCORD_TOKEN")
assert TOKEN is not None, "DISCORD_TOKEN が設定されていません"
bot.run(TOKEN)
