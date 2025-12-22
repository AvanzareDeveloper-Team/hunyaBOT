import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View
from bot.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

OAUTH_URL = (
    "https://discord.com/api/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    "&response_type=code"
    "&scope=identify"
)

class Auth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.roles = {}

    @app_commands.command(name="auth")
    async def auth(self, interaction: discord.Interaction):
        class V(View):
            @discord.ui.button(label="認証する", style=discord.ButtonStyle.blurple)
            async def b(self, i: discord.Interaction, _):
                await i.response.send_message(OAUTH_URL, ephemeral=True)
        await interaction.response.send_message("認証を開始します", view=V(), ephemeral=True)

    @app_commands.command(name="verify")
    async def verify(self, interaction: discord.Interaction, code: str):
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                }
            ) as r:
                data = await r.json()

        if "access_token" not in data:
            return await interaction.response.send_message("認証失敗", ephemeral=True)

        role_id = self.roles.get(interaction.guild.id)
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                await interaction.user.add_roles(role)

        await interaction.response.send_message("認証完了", ephemeral=True)

    @app_commands.command(name="set_auth_role")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_auth_role(self, interaction: discord.Interaction, role: discord.Role):
        self.roles[interaction.guild.id] = role.id
        await interaction.response.send_message("認証ロール設定完了", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Auth(bot))
