import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os

COOLDOWN_FILE = "cooldowns.json"

# Load cooldowns from JSON
def load_cooldowns():
    if not os.path.exists(COOLDOWN_FILE):
        return {}
    with open(COOLDOWN_FILE, "r") as f:
        raw_data = json.load(f)
        cooldowns = {}
        for user, timestamp in raw_data.items():
            cooldowns[user] = datetime.datetime.fromtimestamp(timestamp)
        return cooldowns

# Save cooldowns to JSON
def save_cooldowns(cooldowns):
    raw_data = {user: int(time.timestamp()) for user, time in cooldowns.items()}
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(raw_data, f)

# Cooldown database
promotion_db = load_cooldowns()

class Promote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="promote", description="Promote a Roblox user with a cooldown timer.")
    @app_commands.describe(
        roblox_username="The Roblox username to promote",
        old_rank="Current rank of the user",
        new_rank="New rank of the user",
        cooldown="Cooldown in hours (0 if no cooldown)"
    )
    async def promote(self, interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: float):
        now = datetime.datetime.utcnow()

        if roblox_username in promotion_db:
            cooldown_end = promotion_db[roblox_username]
            if now < cooldown_end:
                timestamp = int(cooldown_end.timestamp())
                await interaction.response.send_message(
                    f"❌ {roblox_username} is still on cooldown! They can be promoted again <t:{timestamp}:R>.", ephemeral=True)
                return

        # Set cooldown if provided
        if cooldown > 0:
            cooldown_end_time = now + datetime.timedelta(hours=cooldown)
            promotion_db[roblox_username] = cooldown_end_time
        else:
            promotion_db.pop(roblox_username, None)

        save_cooldowns(promotion_db)

        embed = discord.Embed(
            title="✅ Promotion Successful!",
            color=discord.Color.green(),
            timestamp=now
        )
        embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
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
