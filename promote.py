import discord
from discord import app_commands
from discord.ext import commands
import datetime

# In-memory database to track promotion cooldowns
promotion_db = {}  # Example: { "RobloxUsername": datetime.datetime }

class Promote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="promote", description="Promote a Roblox user to a new rank with cooldown tracking.")
    @app_commands.describe(
        roblox_username="The Roblox username to promote",
        old_rank="The user's current rank",
        new_rank="The new rank after promotion",
        cooldown="Cooldown in hours before the user can be promoted again (use 0 for no cooldown)"
    )
    async def promote(self, interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: float):
        now = datetime.datetime.utcnow()

        # Check if the user has an active cooldown
        if roblox_username in promotion_db:
            cooldown_end = promotion_db[roblox_username]
            if now < cooldown_end:
                # Cooldown is still active
                timestamp = int(cooldown_end.timestamp())
                await interaction.response.send_message(
                    f"❌ {roblox_username} is still on cooldown! Please wait until <t:{timestamp}:R>.", ephemeral=True)
                return

        # Set new cooldown if needed
        if cooldown > 0:
            cooldown_end_time = now + datetime.timedelta(hours=cooldown)
            promotion_db[roblox_username] = cooldown_end_time
        else:
            promotion_db.pop(roblox_username, None)  # No cooldown needed

        # Create a nice embed for the promotion result
        embed = discord.Embed(
            title="✅ Promotion Successful!",
            color=discord.Color.green()
        )
        embed.add_field(name="Roblox User", value=roblox_username, inline=True)
        embed.add_field(name="Old Rank", value=old_rank, inline=True)
        embed.add_field(name="New Rank", value=new_rank, inline=True)
        
        if cooldown > 0:
            timestamp = int((now + datetime.timedelta(hours=cooldown)).timestamp())
            embed.add_field(name="Next Promotion Available", value=f"<t:{timestamp}:R>", inline=False)
        else:
            embed.add_field(name="Next Promotion Available", value="Immediate (No cooldown)", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Promote(bot))
