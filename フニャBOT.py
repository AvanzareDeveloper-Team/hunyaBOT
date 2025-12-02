import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import io
import aiohttp

# ==========================
# BOT初期設定
# ==========================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"global_channels": {}, "economy": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

app_data = load_data()

# ==========================
# グローバルチャット系
# ==========================
class GlobalChat(app_commands.Group):
    def __init__(self):
        super().__init__(name="global", description="グローバルチャット関連コマンド")

    @app_commands.command(name="create", description="グローバルチャット作成")
    async def global_create(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if name in app_data["global_channels"]:
            await interaction.followup.send("すでに存在しています", ephemeral=True)
            return
        app_data["global_channels"][name] = []
        save_data(app_data)
        await interaction.followup.send(f"グローバルチャット `{name}` を作成しました", ephemeral=True)

    @app_commands.command(name="join", description="グローバルチャットに参加")
    async def global_join(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if name not in app_data["global_channels"]:
            await interaction.followup.send("存在しないチャットです", ephemeral=True)
            return
        channel_id = str(interaction.channel.id)
        if channel_id in app_data["global_channels"][name]:
            await interaction.followup.send("すでに参加済みです", ephemeral=True)
            return
        app_data["global_channels"][name].append(channel_id)
        save_data(app_data)
        await interaction.followup.send(f"このチャンネルを `{name}` に参加させました", ephemeral=True)

    @app_commands.command(name="leave", description="グローバルチャットから脱退")
    async def global_leave(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if name not in app_data["global_channels"]:
            await interaction.followup.send("存在しないチャットです", ephemeral=True)
            return
        channel_id = str(interaction.channel.id)
        if channel_id not in app_data["global_channels"][name]:
            await interaction.followup.send("参加していません", ephemeral=True)
            return
        app_data["global_channels"][name].remove(channel_id)
        save_data(app_data)
        await interaction.followup.send(f"このチャンネルを `{name}` から脱退させました", ephemeral=True)

bot.tree.add_command(GlobalChat())

# ==========================
# メッセージ転送イベント
# ==========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    for chat_name, channels in app_data["global_channels"].items():
        if str(message.channel.id) in channels:
            for ch_id in channels:
                if ch_id == str(message.channel.id):
                    continue
                try:
                    target = bot.get_channel(int(ch_id))
                    if target is None:
                        continue

                    # メッセージ本文
                    content = f"**{message.guild.name} / {message.channel.name}**\n{message.author.name}: {message.content}"

                    # 添付ファイル
                    files = []
                    for attachment in message.attachments:
                        fp = io.BytesIO()
                        await attachment.save(fp)
                        fp.seek(0)
                        files.append(discord.File(fp, filename=attachment.filename))

                    await target.send(content, files=files)
                except Exception as e:
                    print(f"転送失敗: {e}")

# ==========================
# 経済系コマンド
# ==========================
class Economy(app_commands.Group):
    def __init__(self):
        super().__init__(name="eco", description="経済・お金関連")

    def get_balance(self, user_id):
        return app_data["economy"].get(str(user_id), 0)

    def add_money(self, user_id, amount):
        uid = str(user_id)
        app_data["economy"][uid] = app_data["economy"].get(uid, 0) + amount
        save_data(app_data)

    @app_commands.command(name="balance", description="自分の残高を確認")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        bal = self.get_balance(interaction.user.id)
        await interaction.followup.send(f"あなたの残高: {bal} 💰", ephemeral=True)

    @app_commands.command(name="give", description="他人にお金を送る")
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await interaction.response.defer(ephemeral=True)
        if amount <= 0:
            await interaction.followup.send("送金額は正の数で入力してください", ephemeral=True)
            return
        if self.get_balance(interaction.user.id) < amount:
            await interaction.followup.send("残高が不足しています", ephemeral=True)
            return
        self.add_money(interaction.user.id, -amount)
        self.add_money(member.id, amount)
        await interaction.followup.send(f"{member.name} に {amount} 💰 を送金しました", ephemeral=True)

bot.tree.add_command(Economy())

# ==========================
# 雑談系コマンド
# ==========================
class Chat(app_commands.Group):
    def __init__(self):
        super().__init__(name="chat", description="雑談・ミニBOT応答")

    @app_commands.command(name="hello", description="挨拶")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(f"こんにちは {interaction.user.name}！", ephemeral=True)

bot.tree.add_command(Chat())

# ==========================
# ゲーム系コマンド
# ==========================
class Game(app_commands.Group):
    def __init__(self):
        super().__init__(name="game", description="簡単なミニゲーム")

    @app_commands.command(name="roll", description="サイコロを振る")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        await interaction.response.defer(ephemeral=True)
        if sides < 2:
            await interaction.followup.send("サイコロの目は2以上にしてください", ephemeral=True)
            return
        result = random.randint(1, sides)
        await interaction.followup.send(f"🎲 {sides}面サイコロを振りました → {result}", ephemeral=True)

bot.tree.add_command(Game())

# ==========================
# 起動
# ==========================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (完全グローバルBOT)")

bot.run("YOUR_TOKEN_HERE")
