# pyright: reportMissingImports=false
import discord
from discord.ext import commands
from discord import app_commands, ui
from discord.ui import View, Button
import json
import os
from datetime import datetime, timezone
import aiohttp
from flask import Flask, request
import threading

# =================== Flask ===================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    return f"認証コードを受け取りました: {code}"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask, daemon=True).start()

# =================== データファイル ===================
DATA_FILE = "global_chat_data.json"
ECON_FILE = "economy_data.json"
SHOP_FILE = "shop_data.json"
STATS_FILE = "stats.json"
AUTH_FILE = "auth_settings.json"

def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)

data = load_json(DATA_FILE, {"global_channels": {}})
economy_data = load_json(ECON_FILE, {"balances": {}, "daily_message_count": {}})
shop_data = load_json(SHOP_FILE, {})
stats_data = load_json(STATS_FILE, {})
auth_data = load_json(AUTH_FILE, {})

# =================== Bot ===================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# =================== グローバルチャット ===================
async def broadcast_global_message(channel, author, content, attachments):
    for ch_list in data.get("global_channels", {}).values():
        for tgt in ch_list:
            tgt_guild_id, tgt_ch_id = map(int, tgt.split(":"))
            if tgt_guild_id == channel.guild.id and tgt_ch_id == channel.id:
                continue
            tgt_guild = bot.get_guild(tgt_guild_id)
            tgt_channel = tgt_guild.get_channel(tgt_ch_id) if tgt_guild else None
            if tgt_channel:
                embed = discord.Embed(description=content or "(添付のみ)", color=discord.Color.blue())
                embed.set_author(name=f"{author.display_name}@{channel.guild.name}", icon_url=author.display_avatar.url)
                await tgt_channel.send(embed=embed)
                for a in attachments:
                    await tgt_channel.send(a.url)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    guild_id_str = str(message.guild.id) if message.guild else None
    today_str = message.created_at.astimezone(timezone.utc).date().isoformat()

    # --- 統計 ---
    if message.guild:
        stats_data.setdefault("daily_messages", {})
        guild_daily = stats_data["daily_messages"].setdefault(guild_id_str, {})
        guild_daily[today_str] = guild_daily.get(today_str, 0) + 1
        stats_data["daily_messages"][guild_id_str] = guild_daily
        save_json(STATS_FILE, stats_data)

    # --- 経済 ---
    if message.guild:
        economy_data.setdefault("daily_message_count", {})
        user_counts = economy_data["daily_message_count"].setdefault(str(message.author.id), {})
        count_today = user_counts.get(today_str, 0) + 1
        user_counts[today_str] = count_today
        if count_today % 3 == 0:
            economy_data.setdefault("balances", {})
            economy_data["balances"][str(message.author.id)] = economy_data["balances"].get(str(message.author.id), 0) + 1
        save_json(ECON_FILE, economy_data)

    # --- グローバルチャット送信 ---
    if message.guild:
        for ch_list in data.get("global_channels", {}).values():
            identifier = f"{guild_id_str}:{message.channel.id}"
            if identifier in ch_list:
                await broadcast_global_message(message.channel, message.author, message.content, message.attachments)

    await bot.process_commands(message)

# =================== グローバルチャットコマンド ===================
@bot.tree.command(name="global_create", description="グローバルチャット作成")
async def global_create(interaction: discord.Interaction, name: str):
    if name in data["global_channels"]:
        await interaction.response.send_message("既に存在します", ephemeral=True)
        return
    data["global_channels"][name] = []
    save_json(DATA_FILE, data)
    await interaction.response.send_message(f"グローバルチャット `{name}` 作成", ephemeral=True)

@bot.tree.command(name="global_join", description="このチャンネルをグローバルチャットに参加公式はhunya")
async def global_join(interaction: discord.Interaction, name: str):
    ch = interaction.channel
    guild_id_str = str(ch.guild.id)
    if name not in data["global_channels"]:
        await interaction.response.send_message("存在しないグローバルチャットです", ephemeral=True)
        return
    identifier = f"{guild_id_str}:{ch.id}"
    if identifier in data["global_channels"][name]:
        await interaction.response.send_message("既に参加済みです", ephemeral=True)
        return
    data["global_channels"][name].append(identifier)
    save_json(DATA_FILE, data)
    await interaction.response.send_message(f"このチャンネルを `{name}` に参加させました", ephemeral=True)

# =================== 経済・ショップコマンド ===================
@bot.tree.command(name="balance", description="自分のコイン残高を確認")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    bal = economy_data.get("balances", {}).get(user_id, 0)
    await interaction.response.send_message(f" あなたのコイン: {bal}", ephemeral=True)

@bot.tree.command(name="shop_add", description="ロール商品を登録")
@app_commands.describe(role="登録したいロール", price="値段（コイン）")
async def shop_add(interaction: discord.Interaction, role: discord.Role, price: int):
    shop_data[str(role.id)] = price
    save_json(SHOP_FILE, shop_data)
    await interaction.response.send_message(f"{role.name} を {price} コインで登録しました！")

@bot.tree.command(name="shop_buy", description="ロールをコインで購入")
async def shop_buy(interaction: discord.Interaction, role: discord.Role):
    user_id = str(interaction.user.id)
    price = shop_data.get(str(role.id))
    if price is None:
        await interaction.response.send_message("このロールはショップにありません", ephemeral=True)
        return
    bal = economy_data.get("balances", {}).get(user_id, 0)
    if bal < price:
        await interaction.response.send_message("コインが足りません", ephemeral=True)
        return
    try:
        await interaction.user.add_roles(role)
        economy_data["balances"][user_id] -= price
        save_json(ECON_FILE, economy_data)
        await interaction.response.send_message(f"ロール `{role.name}` を購入しました", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("権限不足でロールを付与できません", ephemeral=True)

@bot.tree.command(name="coin_ranking", description="コインのランキングを表示します")
async def coin_ranking(interaction: discord.Interaction):
    balances = economy_data.get("balances", {})
    if not balances:
        await interaction.response.send_message("まだコインを持っている人がいません。")
        return
    top_users = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    ranking_text = ""
    for i, (user_id, coins) in enumerate(top_users, start=1):
        user = interaction.guild.get_member(int(user_id)) if interaction.guild else None
        username = user.display_name if user else f"User({user_id})"
        ranking_text += f"{i}位: {username} — {coins}コイン\n"
    await interaction.response.send_message(f" コインランキング \n{ranking_text}")

# =================== DM ===================
@bot.tree.command(name="dm", description="指定したユーザーIDにDMを送ります")
@app_commands.describe(user_id="DMを送りたい相手のユーザーID", message="DMの内容")
async def dm(interaction: discord.Interaction, user_id: str, message: str):
    try:
        uid = int(user_id)
    except:
        return await interaction.response.send_message("❌ ユーザーIDは数字で入力してね", ephemeral=True)
    user = bot.get_user(uid)
    if not user:
        try:
            user = await bot.fetch_user(uid)
        except:
            return await interaction.response.send_message("❌ ユーザーが見つかりませんでした", ephemeral=True)
    try:
        await user.send(message)
        await interaction.response.send_message(f"📩 {user} にDMを送りました", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ DMを送れません（相手が閉じてる可能性）", ephemeral=True)

# =================== 認証関連 ===================
CLIENT_ID = "1445209748176896091"
CLIENT_SECRET = "v0ScTzJKCBuWcTKsPmL_f5Aafvnme4P_"
REDIRECT_URI = "https://e6f8eb51-bf0a-40d9-87ed-62f9c864e975-00-2rgefl7y9iyw7.riker.replit.dev:8080/callback"
OAUTH_URL = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
BANNED_GUILDS = [
    1193327216642244778, 1313417956473966662, 1426163084468289589,
    1403496250715803790, 1054832544845135934, 123617928892551299,
    1430524783237529603, 1420924251824848988, 1418360870878318752,
    1422851492452372582, 1433015067086964617, 1417875141169512498
]

@bot.tree.command(name="set_auth_role", description="認証後に付与するロールを設定（管理者専用）")
@app_commands.checks.has_permissions(administrator=True)
async def set_auth_role(interaction: discord.Interaction, role: discord.Role):
    gid = str(interaction.guild.id)
    auth_data[gid] = {"auth_role": role.id}
    save_json(AUTH_FILE, auth_data)
    await interaction.response.send_message(f"認証ロールを `{role.name}` に設定しました！", ephemeral=True)

@bot.tree.command(name="auth", description="アカウント認証を開始します")
async def auth(interaction: discord.Interaction):
    class AuthButton(View):
        def __init__(self):
            super().__init__(timeout=None)

        @ui.button(label="認証を開始する", style=discord.ButtonStyle.blurple)
        async def start_auth(self, i: discord.Interaction, b: Button):
            await i.response.send_message(f"👇 こちらのリンクから認証してください！\n{OAUTH_URL}", ephemeral=True)

    await interaction.response.send_message("アカウント認証を開始します。以下のボタンを押してください。", view=AuthButton(), ephemeral=True)

@bot.tree.command(name="verify", description="認証済みか確認しロールを付与します")
async def verify(interaction: discord.Interaction, code: str):
    token_url = "https://discord.com/api/oauth2/token"
    data_post = {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type":"authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data_post) as resp:
            token_data = await resp.json()
    if "access_token" not in token_data:
        return await interaction.response.send_message("認証に失敗しました。", ephemeral=True)
    access_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
            guilds_info = await resp.json()
    for g in guilds_info:
        if int(g["id"]) in BANNED_GUILDS:
            await interaction.guild.ban(interaction.user, reason="禁止サーバーに参加していたため")
            return await interaction.response.send_message("❌ 認証失敗：禁止サーバーに参加しています。", ephemeral=True)
    gid = str(interaction.guild.id)
    if gid not in auth_data or "auth_role" not in auth_data[gid]:
        return await interaction.response.send_message("認証ロールが設定されていません。", ephemeral=True)
    role = interaction.guild.get_role(auth_data[gid]["auth_role"])
    if not role:
        return await interaction.response.send_message("設定された認証ロールが見つかりません。", ephemeral=True)
    try:
        await interaction.user.add_roles(role, reason="認証完了")
    except discord.Forbidden:
        return await interaction.response.send_message("ロールを付与できません（権限不足）。", ephemeral=True)
    await interaction.response.send_message("✅ 認証完了しました！", ephemeral=True)
    print("認証しました")
from discord import Embed
from datetime import datetime

@bot.tree.command(name="help", description="helpを表示します")
async def help(interaction: discord.Interaction):
    embed = Embed(
        title="help",
        description=(
            "auth 認証を開始します\n"
            "verify 認証コードで認証を完了します\n"
            "set_auth_role 認証後に付与するロールを設定します\n"
            "dm ユーザー ID で指定した相手に DM を送信します\n"
            "balance メッセージ送信でたまるコインの残高を確認します\n"
            "shop_add コインで買えるロールを設定します\n"
            "shop_buy コインで買えるロールを買います\n"
            "global_create サーバー間でチャットできるグローバルチャットを作成します\n"
            "global_join 指定した名前のグローバルチャットに参加します\n"
            "公式のグローバルチャットは `hunya` です"
        ),
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    await interaction.response.send_message(embed=embed)
# =================== on_ready ===================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

# =================== Bot 起動 ===================
TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
