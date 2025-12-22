import re, json, os
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands

DATA_DIR = "data"
INVITE_REGEX = r"(discord\.gg|discord\.com\/invite)\/\S+"
URL_REGEX = r"https?://[^\s]+"

def load(name, d):
    p = f"{DATA_DIR}/{name}.json"
    return json.load(open(p,"r",encoding="utf-8")) if os.path.exists(p) else d

def save(name, d):
    json.dump(d, open(f"{DATA_DIR}/{name}.json","w",encoding="utf-8"),
              indent=2, ensure_ascii=False)

invite_cfg = load("invite", {})

class InviteWatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===== メッセージ監視 =====
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        gid = str(message.guild.id)
        cfg = invite_cfg.setdefault(
            gid, {"enabled": False, "ignore": [], "url_watch": False}
        )

        # 例外チャンネル
        if message.channel.id in cfg["ignore"]:
            return

        # 招待リンク監視
        if cfg["enabled"] and re.search(INVITE_REGEX, message.content):
            await message.delete()
            until = datetime.now(timezone.utc) + timedelta(minutes=10)
            await message.author.timeout(until, reason="招待リンク送信")

        # URL監視
        elif cfg["url_watch"] and re.search(URL_REGEX, message.content):
            await message.delete()
            await message.author.send("このチャンネルではURLは禁止されています")

    # ===== 招待リンク ON/OFF =====
    @discord.app_commands.command(name="invite_watch")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def invite_watch(self, interaction: discord.Interaction, enabled: bool):
        cfg = invite_cfg.setdefault(
            str(interaction.guild.id),
            {"enabled": False, "ignore": [], "url_watch": False}
        )
        cfg["enabled"] = enabled
        save("invite", invite_cfg)
        await interaction.response.send_message(
            f"招待リンク監視を {'有効' if enabled else '無効'} にしました",
            ephemeral=True
        )

    # ===== URL監視 ON/OFF =====
    @discord.app_commands.command(name="url_watch")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def url_watch(self, interaction: discord.Interaction, enabled: bool):
        cfg = invite_cfg.setdefault(
            str(interaction.guild.id),
            {"enabled": False, "ignore": [], "url_watch": False}
        )
        cfg["url_watch"] = enabled
        save("invite", invite_cfg)
        await interaction.response.send_message(
            f"URL監視を {'有効' if enabled else '無効'} にしました",
            ephemeral=True
        )

    # ===== 例外チャンネル追加 =====
    @discord.app_commands.command(name="invite_ignore_add")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def invite_ignore_add(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        cfg = invite_cfg.setdefault(
            str(interaction.guild.id),
            {"enabled": False, "ignore": [], "url_watch": False}
        )
        if channel.id not in cfg["ignore"]:
            cfg["ignore"].append(channel.id)
        save("invite", invite_cfg)
        await interaction.response.send_message(
            f"{channel.mention} を例外チャンネルに追加しました",
            ephemeral=True
        )

    # ===== 例外チャンネル削除 =====
    @discord.app_commands.command(name="invite_ignore_remove")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def invite_ignore_remove(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        cfg = invite_cfg.setdefault(
            str(interaction.guild.id),
            {"enabled": False, "ignore": [], "url_watch": False}
        )
        if channel.id in cfg["ignore"]:
            cfg["ignore"].remove(channel.id)
        save("invite", invite_cfg)
        await interaction.response.send_message(
            f"{channel.mention} を監視対象に戻しました",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(InviteWatch(bot))
