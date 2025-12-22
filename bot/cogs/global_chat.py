import json
import os
import discord
from discord.ext import commands

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

global_data = load("global", {})

class GlobalChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===============================
    # メッセージ中継
    # ===============================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        identifier = f"{message.guild.id}:{message.channel.id}"

        for name, chans in global_data.items():
            if identifier not in chans:
                continue

            for target in chans:
                if target == identifier:
                    continue

                tg, tc = map(int, target.split(":"))
                guild = self.bot.get_guild(tg)
                if not guild:
                    continue

                channel = guild.get_channel(tc)
                if not channel:
                    continue

                await channel.send(
                    f"**{message.author.display_name}@{message.guild.name}**\n"
                    f"{message.content}"
                )

    # ===============================
    # /global_create
    # ===============================
    @discord.app_commands.command(name="global_create")
    async def global_create(self, interaction: discord.Interaction, name: str):
        if name not in global_data:
            global_data[name] = []
            save("global", global_data)

        await interaction.response.send_message(
            "✅ グローバルチャットを作成しました",
            ephemeral=True
        )

    # ===============================
    # /global_join
    # ===============================
    @discord.app_commands.command(name="global_join")
    async def global_join(self, interaction: discord.Interaction, name: str):
        identifier = f"{interaction.guild.id}:{interaction.channel.id}"
        chans = global_data.setdefault(name, [])

        if identifier not in chans:
            chans.append(identifier)
            save("global", global_data)

        await interaction.response.send_message(
            "✅ グローバルチャットに参加しました",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(GlobalChatCog(bot))
