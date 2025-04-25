import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask
from typing import List, Dict
from urllib.parse import quote  # Use urllib.parse for URL encoding

from datetime import timedelta

rank_cooldowns = {
    ("El3", "El4"): timedelta(hours=2),
    ("El4", "El5"): timedelta(hours=2),
    ("El5", "El6"): timedelta(seconds=0),
    ("El6", "El7"): timedelta(hours=48),
    ("El7", "El8"): timedelta(hours=72),
    ("El8", "El9"): timedelta(hours=120)
}

valid_ranks = ["El1", "El2", "El3", "El4", "El5", "El6", "El7", "El8", "El9"]

# Tracks last promotion times
promotion_timestamps: Dict[str, Dict[str, datetime.datetime]] = {}

# Flask app for port binding (Render requirement)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    # Get the port from environment variable or set to a default port (e.g., 8080)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# Set up bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Promotion database
promotion_db = {}

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

@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(
    roblox_username="The Roblox username of the user to promote",
    old_rank="The user's current rank",
    new_rank="The new rank after promotion"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str):
    await interaction.response.defer()

    # Validate ranks
    if old_rank not in valid_ranks or new_rank not in valid_ranks:
        await interaction.followup.send("Invalid rank or promotion request.", ephemeral=True)
        return
    if valid_ranks.index(new_rank) <= valid_ranks.index(old_rank):
        await interaction.followup.send("You cannot promote to the same or lower rank.", ephemeral=True)
        return

    cooldown_key = (old_rank, new_rank)
    current_time = datetime.datetime.now()

    last_promotion_time = promotion_timestamps.get(roblox_username, {}).get(old_rank)
    cooldown = rank_cooldowns.get(cooldown_key)

    if cooldown is not None and last_promotion_time:
        elapsed = current_time - last_promotion_time
        if elapsed < cooldown:
            remaining = cooldown - elapsed

            # Create an embed to show the remaining time in an orange box
            embed = discord.Embed(
                title="⏳ Promotion Cooldown",
                description=f"**Time remaining before next promotion:**\n`{str(remaining).split('.')[0]}`",
                color=discord.Color.orange()
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    # Track the promotion time
    if roblox_username not in promotion_timestamps:
        promotion_timestamps[roblox_username] = {}
    promotion_timestamps[roblox_username][old_rank] = current_time

    # Log promotion
    current_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
    promoter = interaction.user.name
    promotion_entry = {
        "old_rank": old_rank,
        "new_rank": new_rank,
        "date": current_date,
        "promoter": promoter
    }
    if roblox_username not in promotion_db:
        promotion_db[roblox_username] = []
    promotion_db[roblox_username].append(promotion_entry)

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

    # Add cooldown info
    next_key = (new_rank, valid_ranks[valid_ranks.index(new_rank) + 1]) if new_rank != "El9" else None
    if next_key in rank_cooldowns:
        next_cd = rank_cooldowns[next_key]
        embed.set_footer(text=f"Cooldown for next promotion: {next_cd}")
    elif new_rank == "El9":
        embed.set_footer(text="User is at the highest rank (El9). No further promotions available.")

    await interaction.followup.send(embed=embed)
# Run the bot using environment variable
bot.run(os.getenv("DISCORD_TOKEN"))
