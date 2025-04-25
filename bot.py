import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask
from typing import Dict

# Flask app for port binding (Render requirement)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# Set up bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Promotion database to track timestamps
promotion_db = {}

# Cooldown settings for each category and rank transition
cooldowns = {
    "medical": {
        "El3 medical": {"El4 medical": 2 * 60 * 60},  # 2 hours
        "El4 medical": {"El5 medical": 12 * 60 * 60},  # 12 hours
        "El5 medical": {"El6 medical": 0},  # No cooldown
        "El6 medical": {"El7 medical": 48 * 60 * 60},  # 48 hours
        "El7 medical": {"El8 medical": 72 * 60 * 60},  # 72 hours
        "El8 medical": {"El9 medical": 120 * 60 * 60},  # 120 hours
    },
    "receptionist": {
        "El3 receptionist": {"El4 receptionist": 2 * 60 * 60},  # 2 hours
        "El4 receptionist": {"El5 receptionist": 12 * 60 * 60},  # 12 hours
        "El5 receptionist": {"El6 receptionist": 0},  # No cooldown
        "El6 receptionist": {"El7 receptionist": 48 * 60 * 60},  # 48 hours
        "El7 receptionist": {"El8 receptionist": 72 * 60 * 60},  # 72 hours
        "El8 receptionist": {"El9 receptionist": 120 * 60 * 60},  # 120 hours
    },
    "nurse": {
        "El3 nurse": {"El4 nurse": 2 * 60 * 60},  # 2 hours
        "El4 nurse": {"El5 nurse": 12 * 60 * 60},  # 12 hours
        "El5 nurse": {"El6 nurse": 0},  # No cooldown
        "El6 nurse": {"El7 nurse": 48 * 60 * 60},  # 48 hours
        "El7 nurse": {"El8 nurse": 72 * 60 * 60},  # 72 hours
        "El8 nurse": {"El9 nurse": 120 * 60 * 60},  # 120 hours
    },
    "surgical": {
        "El3 surgical": {"El4 surgical": 2 * 60 * 60},  # 2 hours
        "El4 surgical": {"El5 surgical": 12 * 60 * 60},  # 12 hours
        "El5 surgical": {"El6 surgical": 0},  # No cooldown
        "El6 surgical": {"El7 surgical": 48 * 60 * 60},  # 48 hours
        "El7 surgical": {"El8 surgical": 72 * 60 * 60},  # 72 hours
        "El8 surgical": {"El9 surgical": 120 * 60 * 60},  # 120 hours
    }
}

async def get_roblox_avatar(roblox_username: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.roblox.com/users/get-by-username?username={roblox_username}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    user_id = data.get("Id")
                    if user_id:
                        async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png&isCircular=false") as thumb_resp:
                            if thumb_resp.status == 200:
                                thumb_data = await thumb_resp.json()
                                return thumb_data["data"][0]["imageUrl"]
    except Exception as e:
        print(f"Error fetching Roblox avatar: {e}")
    return None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Command for promoting
@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(
    roblox_username="The Roblox username of the user to promote",
    old_rank="The user's current rank",
    new_rank="The new rank after promotion",
    category="The category of the user (medical, receptionist, nurse, surgical)"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, category: str):
    await interaction.response.defer()

    # Ensure category is valid
    if category not in cooldowns:
        await interaction.followup.send("Invalid category. Use 'medical', 'receptionist', 'nurse', or 'surgical'.")
        return

    # Check cooldown
    current_time = datetime.datetime.now().timestamp()  # Current time in seconds
    if roblox_username in promotion_db and category in promotion_db[roblox_username]:
        last_promotion_time = promotion_db[roblox_username][category].get(old_rank)
        if last_promotion_time:
            time_since_last_promotion = current_time - last_promotion_time
            cooldown_time = cooldowns[category].get(old_rank, {}).get(new_rank, 0)

            # Check if cooldown is still active
            if time_since_last_promotion < cooldown_time:
                remaining_time = cooldown_time - time_since_last_promotion
                remaining_time_minutes = remaining_time // 60
                embed = discord.Embed(
                    title=f"⚠️ Cooldown Active for {roblox_username}",
                    description=f"Please wait {remaining_time_minutes} minutes before promoting again.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return

    # Proceed with promotion
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    promoter = interaction.user.name

    # Log promotion time in the database
    if roblox_username not in promotion_db:
        promotion_db[roblox_username] = {}

    if category not in promotion_db[roblox_username]:
        promotion_db[roblox_username][category] = {}

    promotion_db[roblox_username][category][old_rank] = current_time

    # Get user avatar
    avatar_url = await get_roblox_avatar(roblox_username)
    embed = discord.Embed(
        title=f"🎉 Promotion for {roblox_username}",
        color=discord.Color.green()
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="Previous Rank", value=old_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)
    embed.add_field(name="Promoted By", value=promoter, inline=False)
    embed.add_field(name="Date", value=current_date, inline=False)

    await interaction.followup.send(embed=embed)

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
