import json
import os
import aiohttp
import discord
from discord.ext import commands
from discord.ui import View, Button
from flask import request

from bot.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

DATA_DIR = "data"

def load(name, default):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save(name, data):
    with open(os.path.join(DATA_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

auth_data = load("auth", {})

OAUTH_URL = (
    "https://discord.com/api/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    "&response_type=code"
    "&scope=identify%20guilds"
)

class AuthCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===============================
    # /auth 認証ボタン
    # ===============================
    @discord.app_commands.command(name="auth")
    async def auth(self, interaction: discord.Interaction):

        class AuthView(View):
            @discord.ui.button(label="認証する", style=discord.ButtonStyle.blurple)
            async def auth_button(self, i: discord.Interaction, _):
                await i.response.send_message(OAUTH_URL, ephemeral=True)

        await interaction.response.send_message(
            "ボタンを押して認証してください",
            view=AuthView(),
            ephemeral=True
        )

    # ===============================
    # /verify 認証コード処理
    # ===============================
    @discord.app_commands.command(name="verify")
    async def verify(self, interaction: discord.Interaction, code: str):
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
            await interaction.followup.send("❌ 認証に失敗しました")
            return

        guild_id = str(interaction.guild.id)
        role_id = auth_data.get(guild_id)
        role = interaction.guild.get_role(role_id) if role_id else None

        if role:
            await interaction.user.add_roles(role)
            await interaction.followup.send("✅ 認証完了！ロールを付与しました")
        else:
            await interaction.followup.send("⚠️ 認証ロールが設定されていません")

    # ===============================
    # /set_auth_role 管理者用
    # ===============================
    @discord.app_commands.command(name="set_auth_role")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_auth_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        auth_data[str(interaction.guild.id)] = role.id
        save("auth", auth_data)
        await interaction.response.send_message(
            "✅ 認証ロールを設定しました",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(AuthCog(bot))
