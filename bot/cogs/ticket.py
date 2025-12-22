import discord
from discord.ext import commands
from discord.ui import View, Button

class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    class TicketView(View):
        @discord.ui.button(label="🎫 チケット作成", style=discord.ButtonStyle.green)
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

            class CloseView(View):
                @discord.ui.button(label="❌ チケットを閉じる", style=discord.ButtonStyle.red)
                async def close(self, inter: discord.Interaction, _):
                    await inter.response.send_message("削除します", ephemeral=True)
                    await ch.delete()

            await ch.send(f"{i.user.mention} のチケット", view=CloseView())
            await i.response.send_message("作成しました", ephemeral=True)

    @discord.app_commands.command(name="ticket_panel")
    async def ticket_panel(self, interaction: discord.Interaction):
        await interaction.response.send_message("チケット作成", view=self.TicketView())

async def setup(bot):
    await bot.add_cog(TicketCog(bot))
