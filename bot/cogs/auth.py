import os
import json
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from urllib.parse import quote

from bot.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

OWNER_ID = 123456789012345678  # ← 自分のDiscord IDに変更
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

BANNED_GUILDS_PATH = os.path.join(DATA_DIR, "banned_guilds.json")
AUTO_ROLES_PATH = os.path.join(DATA_DIR, "auto_roles.json")

# ===============================
# JSONユーティリティ
# ===============================
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ===============================
# AuthCog
# ===============================
class AuthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- データ ----------
    def load_banned_guilds(self) -> set[str]:
        return set(load_json(BANNED_GUILDS_PATH, []))

    def save_banned_guilds(self, data: set[str]):
        save_json(BANNED_GUILDS_PATH, list(data))

    def load_auto_roles(self) -> dict[str, str]:
        return load_json(AUTO_ROLES_PATH, {})

    def save_auto_roles(self, data: dict[str, str]):
        save_json(AUTO_ROLES_PATH, data)

    # ---------- OAuth ----------
    def make_oauth_url(self, user_id: int, guild_id: int) -> str:
        redirect_uri = quote(f"{REDIRECT_URI}/callback", safe="")
        state = f"{user_id}:{guild_id}"
        return (
            "https://discord.com/api/oauth2/authorize"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code"
            "&scope=identify%20guilds"
            f"&state={state}"
        )

    @app_commands.command(name="auth", description="OAuth認証を行います")
    async def auth(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            if not interaction.guild:
                await interaction.followup.send("❌ サーバー内で実行してください", ephemeral=True)
                return

            url = self.make_oauth_url(interaction.user.id, interaction.guild.id)
            await interaction.followup.send(f"🔐 **以下のURLから認証してください**\n{url}", ephemeral=True)

        except Exception as e:
            print(f"[AuthCog] /auth コマンドエラー: {e}")

    # ---------- OAuth callback handler ----------
    async def handle_oauth(self, code: str, user_id: int, guild_id: int):
        try:
            async with aiohttp.ClientSession() as session:
                token_resp = await session.post(
                    "https://discord.com/api/oauth2/token",
                    data={
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": f"{REDIRECT_URI}/callback",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                token_data = await token_resp.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    print("[AuthCog] アクセストークン取得失敗")
                    return

                guilds_resp = await session.get(
                    "https://discord.com/api/users/@me/guilds",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                user_guilds = await guilds_resp.json()

            # 禁止サーバー判定
            banned = self.load_banned_guilds()
            if any(str(g["id"]) in banned for g in user_guilds):
                await self.ban_user(user_id, guild_id)
                return

            # 自動ロール付与
            await self.give_auto_role(user_id, guild_id)

        except Exception as e:
            print(f"[AuthCog] OAuth処理エラー: {e}")

    # ---------- BAN ----------
    async def ban_user(self, user_id: int, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            print(f"[AuthCog] ban失敗: ギルド取得できず {guild_id}")
            return
        try:
            member = guild.get_member(user_id)
            if not member:
                member = await guild.fetch_member(user_id)
            if member:
                await member.ban(reason="禁止サーバーに参加しているため")
                print(f"[AuthCog] {member} をBANしました")
        except Exception as e:
            print(f"[AuthCog] banエラー: {e}")

    # ---------- 自動ロール ----------
    async def give_auto_role(self, user_id: int, guild_id: int):
        auto_roles = self.load_auto_roles()
        role_id = auto_roles.get(str(guild_id))
        if not role_id:
            print(f"[AuthCog] 自動ロール未設定: guild={guild_id}")
            return
        guild = self.bot.get_guild(guild_id)
        if not guild:
            print(f"[AuthCog] ギルド取得失敗: {guild_id}")
            return
        try:
            member = guild.get_member(user_id)
            if not member:
                member = await guild.fetch_member(user_id)

            role = guild.get_role(int(role_id))
            if not role:
                print(f"[AuthCog] ロール取得失敗: {role_id}")
                return

            await member.add_roles(role, reason="OAuth認証完了")
            print(f"[AuthCog] {member} にロール {role.name} を付与しました")
        except Exception as e:
            print(f"[AuthCog] 自動ロール付与エラー: {e}")

    # ===============================
    # 管理コマンド
    # ===============================
    banned = app_commands.Group(name="banned", description="禁止サーバー管理（BOTオーナー専用）")

    @banned.command(name="add")
    async def banned_add(self, interaction: discord.Interaction, guild_id: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != OWNER_ID:
            await interaction.followup.send("❌ 権限なし", ephemeral=True)
            return
        data = self.load_banned_guilds()
        data.add(guild_id)
        self.save_banned_guilds(data)
        await interaction.followup.send("✅ 追加しました", ephemeral=True)

    @banned.command(name="remove")
    async def banned_remove(self, interaction: discord.Interaction, guild_id: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != OWNER_ID:
            await interaction.followup.send("❌ 権限なし", ephemeral=True)
            return
        data = self.load_banned_guilds()
        data.discard(guild_id)
        self.save_banned_guilds(data)
        await interaction.followup.send("✅ 削除しました", ephemeral=True)

    @banned.command(name="list")
    async def banned_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != OWNER_ID:
            await interaction.followup.send("❌ 権限なし", ephemeral=True)
            return
        data = self.load_banned_guilds()
        msg = "\n".join(data) if data else "なし"
        await interaction.followup.send(msg, ephemeral=True)

    # ---------- 自動ロール設定 ----------
    @app_commands.command(
        name="set_auth_role",
        description="認証後に付与するロールを設定（管理者専用）"
    )
    async def set_auth_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("❌ サーバー内で実行してください", ephemeral=True)
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ 管理者権限が必要です", ephemeral=True)
            return

        data = self.load_auto_roles()
        data[str(interaction.guild.id)] = str(role.id)
        self.save_auto_roles(data)
        await interaction.followup.send(f"✅ 認証後ロールを **{role.name}** に設定しました", ephemeral=True)

# ===============================
# setup
# ===============================
async def setup(bot: commands.Bot):
    await bot.add_cog(AuthCog(bot))
