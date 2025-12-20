import os, json, re, threading
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button

import aiohttp
from flask import Flask, request

# ===============================
# データディレクトリ
# ===============================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(name, default):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(name, data):
    with open(os.path.join(DATA_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

auth_data   = load_json("auth", {})
invite_cfg  = load_json("invite", {})
global_data = load_json("global", {})
economy     = load_json("economy", {"balances": {}})
shop        = load_json("shop", {})

# ===============================
# Flask（OAuth Callback）
# ===============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    return f"認証コード取得：{code} を Discord の /verify に貼り付けてください"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ===============================
# OAuth 設定
# ===============================
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
BOT_TOKEN = "YOUR_BOT_TOKEN"
REDIRECT_URI = "http://127.0.0.1:5000/callback"

OAUTH_URL = (
    "https://discord.com/api/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    "&response_type=code"
    "&scope=identify%20guilds"
)

# ===============================
# Bot
# ===============================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===============================
# 定期保存タスク
# ===============================
@tasks.loop(minutes=5)
async def save_task():
    save_json("auth", auth_data)
    save_json("invite", invite_cfg)
    save_json("global", global_data)
    save_json("economy", economy)
    save_json("shop", shop)

save_task.start()

# ===============================
# 招待リンク＆URL監視＋無視チャンネル対応
# ===============================
INVITE_REGEX = r"(discord\.gg|discord\.com\/invite)\/\S+"
URL_REGEX = r"https?://[^\s]+"

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    cfg = invite_cfg.setdefault(gid, {"enabled": False, "ignore": [], "url_watch": False})

    # 無視チャンネル判定
    if message.channel.id not in cfg.get("ignore", []):
        # 招待リンク
        if cfg.get("enabled") and re.search(INVITE_REGEX, message.content):
            await message.delete()
            until = datetime.now(timezone.utc) + timedelta(minutes=10)
            await message.author.timeout(until, reason="招待リンク送信")
        # URL監視
        elif cfg.get("url_watch") and re.search(URL_REGEX, message.content):
            await message.delete()
            await message.author.send(f"{message.channel.mention} で URL が禁止されています。")

    # グローバルチャット
    identifier = f"{gid}:{message.channel.id}"
    for name, chans in global_data.items():
        if identifier in chans:
            for tgt in chans:
                if tgt == identifier:
                    continue
                tg, tc = map(int, tgt.split(":"))
                g = bot.get_guild(tg)
                if not g:
                    continue
                ch = g.get_channel(tc)
                if ch:
                    await ch.send(
                        f"**{message.author.display_name}@{message.guild.name}**\n{message.content}"
                    )

    await bot.process_commands(message)

# ===============================
# 招待リンク/URL監視 ON/OFF
# ===============================
@bot.tree.command(name="invite_watch")
@discord.app_commands.checks.has_permissions(administrator=True)
async def invite_watch(interaction: discord.Interaction, enabled: bool):
    cfg = invite_cfg.setdefault(str(interaction.guild.id), {"enabled": False, "ignore": [], "url_watch": False})
    cfg["enabled"] = enabled
    save_json("invite", invite_cfg)
    await interaction.response.send_message(f"招待リンク監視を {'有効' if enabled else '無効'} にしました", ephemeral=True)

@bot.tree.command(name="url_watch")
@discord.app_commands.checks.has_permissions(administrator=True)
async def url_watch(interaction: discord.Interaction, enabled: bool):
    cfg = invite_cfg.setdefault(str(interaction.guild.id), {"enabled": False, "ignore": [], "url_watch": False})
    cfg["url_watch"] = enabled
    save_json("invite", invite_cfg)
    await interaction.response.send_message(f"URL監視を {'有効' if enabled else '無効'} にしました", ephemeral=True)

# ===============================
# 無視チャンネル追加/削除
# ===============================
@bot.tree.command(name="invite_ignore_add")
@discord.app_commands.checks.has_permissions(administrator=True)
async def invite_ignore_add(interaction: discord.Interaction, channel: discord.TextChannel):
    cfg = invite_cfg.setdefault(str(interaction.guild.id), {"enabled": False, "ignore": [], "url_watch": False})
    if channel.id not in cfg["ignore"]:
        cfg["ignore"].append(channel.id)
    save_json("invite", invite_cfg)
    await interaction.response.send_message(f"{channel.mention} を監視対象から除外しました", ephemeral=True)

@bot.tree.command(name="invite_ignore_remove")
@discord.app_commands.checks.has_permissions(administrator=True)
async def invite_ignore_remove(interaction: discord.Interaction, channel: discord.TextChannel):
    cfg = invite_cfg.setdefault(str(interaction.guild.id), {"enabled": False, "ignore": [], "url_watch": False})
    if channel.id in cfg["ignore"]:
        cfg["ignore"].remove(channel.id)
    save_json("invite", invite_cfg)
    await interaction.response.send_message(f"{channel.mention} を監視対象に戻しました", ephemeral=True)

# ===============================
# 認証コマンド
# ===============================
@bot.tree.command(name="auth")
async def auth(interaction: discord.Interaction):
    class V(View):
        @Button(label="認証する", style=discord.ButtonStyle.blurple)
        async def b(self, i: discord.Interaction, _):
            await i.response.send_message(OAUTH_URL, ephemeral=True)
    await interaction.response.send_message("ボタンを押して認証", view=V(), ephemeral=True)

@bot.tree.command(name="verify")
async def verify(interaction: discord.Interaction, code: str):
    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            }
        ) as resp:
            token_data = await resp.json()

    if "access_token" not in token_data:
        await interaction.followup.send("認証失敗")
        return

    role_id = auth_data.get(str(interaction.guild.id))
    role = interaction.guild.get_role(role_id) if role_id else None
    if role:
        await interaction.user.add_roles(role)
        await interaction.followup.send("認証完了！ロール付与しました")
    else:
        await interaction.followup.send("認証ロール未設定")

@bot.tree.command(name="set_auth_role")
@discord.app_commands.checks.has_permissions(administrator=True)
async def set_auth_role(interaction: discord.Interaction, role: discord.Role):
    auth_data[str(interaction.guild.id)] = role.id
    save_json("auth", auth_data)
    await interaction.response.send_message("認証ロール設定完了", ephemeral=True)

# ===============================
# チケット作成（ボタン式 + 自動削除ボタン）
# ===============================
class TicketView(View):
    @Button(label="🎫 チケット作成", style=discord.ButtonStyle.green)
    async def open(self, i: discord.Interaction, _):
        cat = discord.utils.get(i.guild.categories, name="Tickets")
        if not cat:
            cat = await i.guild.create_category("Tickets")
        ch = await i.guild.create_text_channel(
            f"ticket-{i.user.name}",
            category=cat,
            overwrites={
                i.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                i.user: discord.PermissionOverwrite(read_messages=True)
            }
        )
        # チャンネル内に削除ボタンを送信
        class CloseView(View):
            @Button(label="❌ チケットを閉じる", style=discord.ButtonStyle.red)
            async def close(self, inter: discord.Interaction, _):
                await inter.response.send_message("チケットを削除します…", ephemeral=True)
                await ch.delete()
        await ch.send(f"{i.user.mention} のチケットです", view=CloseView())
        await i.response.send_message(f"{ch.mention} を作成しました", ephemeral=True)

@bot.tree.command(name="ticket_panel")
async def ticket_panel(interaction: discord.Interaction):
    await interaction.response.send_message("チケット作成", view=TicketView())

# ===============================
# ロールパネル（最大5）
# ===============================
class RolePanel(View):
    def __init__(self, roles):
        super().__init__(timeout=None)
        for r in roles:
            b = Button(label=r.name)
            async def cb(i, role=r):
                if role in i.user.roles:
                    await i.user.remove_roles(role)
                else:
                    await i.user.add_roles(role)
                await i.response.send_message("変更完了", ephemeral=True)
            b.callback = cb
            self.add_item(b)

@bot.tree.command(name="role_panel")
async def role_panel(
    interaction: discord.Interaction,
    r1: discord.Role,
    r2: discord.Role = None,
    r3: discord.Role = None,
    r4: discord.Role = None,
    r5: discord.Role = None
):
    roles = [r for r in [r1,r2,r3,r4,r5] if r]
    await interaction.response.send_message("ロールパネル", view=RolePanel(roles))

# ===============================
# グローバルチャット
# ===============================
@bot.tree.command(name="global_create")
async def global_create(interaction: discord.Interaction, name: str):
    global_data[name] = []
    save_json("global", global_data)
    await interaction.response.send_message("作成完了", ephemeral=True)

@bot.tree.command(name="global_join")
async def global_join(interaction: discord.Interaction, name: str):
    identifier = f"{interaction.guild.id}:{interaction.channel.id}"
    global_data.setdefault(name, []).append(identifier)
    save_json("global", global_data)
    await interaction.response.send_message("参加完了", ephemeral=True)
# ===============================
# ヘルプコマンド（Embed版）
# ===============================
@bot.tree.command(name="help")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="中級Bot コマンド一覧",
        description="以下のコマンドを使用できます",
        color=discord.Color.blue()
    )

    # 認証
    embed.add_field(
        name="認証",
        value="""
/auth - 認証ボタンを表示
/verify <code> - 認証コードでロール付与
/set_auth_role <role> - 認証ロール設定
""",
        inline=False
    )

    # 招待リンク・URL監視
    embed.add_field(
        name="招待リンク・URL監視",
        value="""
/invite_watch <true/false> - 招待リンク監視ON/OFF
/url_watch <true/false> - URL監視ON/OFF
/invite_ignore_add <channel> - 無視チャンネル追加
/invite_ignore_remove <channel> - 無視チャンネル削除
""",
        inline=False
    )

    # チケット
    embed.add_field(
        name="チケット",
        value="/ticket_panel - チケット作成ボタン表示",
        inline=False
    )

    # ロールパネル
    embed.add_field(
        name="ロールパネル",
        value="/role_panel <r1> [r2 r3 r4 r5] - 最大5ロールのロールパネル作成",
        inline=False
    )

    # グローバルチャット
    embed.add_field(
        name="グローバルチャット",
        value="""
/global_create <name> - グローバルチャット作成
/global_join <name> - グローバルチャットに参加
""",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)
@bot.event
async def on_ready():
    # スラッシュコマンド同期
    try:
        synced = await bot.tree.sync()
        print(f"スラッシュコマンド同期完了: {len(synced)}個")
    except Exception as e:
        print("同期エラー:", e)

    # Bot情報表示
    print(f"ログイン完了: {bot.user} (ID: {bot.user.id})")

    # ステータス設定
    await bot.change_presence(
        activity=discord.Game(name="/help でコマンド確認")
    )
# ===============================
# 起動
# ===============================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(BOT_TOKEN)
