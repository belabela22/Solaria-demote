import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask
from typing import List, Dict

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

promotion_cooldowns = {
    ("EL3", "EL4"): 2,
    ("EL4", "EL5"): 12,
    ("EL5", "EL6"): 0,
    ("EL6", "EL7"): 48,
    ("EL7", "EL8"): 72,
    ("EL8", "EL9"): 120,
}

@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(
    roblox_username="The Roblox username of the user to promote",
    old_rank="The user's current rank",
    new_rank="The new rank after promotion"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str):
    await interaction.response.defer()

    # Check cooldown
    key = (old_rank.upper(), new_rank.upper())
    now = datetime.datetime.now()
    cooldown_hours = promotion_cooldowns.get(key)

    if roblox_username in last_promotion_time and cooldown_hours is not None:
        last_time = last_promotion_time[roblox_username]
        delta = now - last_time
        if delta.total_seconds() < cooldown_hours * 3600:
            remaining = cooldown_hours * 3600 - delta.total_seconds()
            hours_left = int(remaining // 3600)
            minutes_left = int((remaining % 3600) // 60)
            embed = discord.Embed(
                title="Promotion Wait",
                description=f"**You must wait {hours_left}h {minutes_left}m** before promoting {roblox_username} to {new_rank}.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            return

    # Continue with promotion
    current_date = now.strftime("%Y-%m-%d %H:%M:%S")
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
    last_promotion_time[roblox_username] = now

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

# Run the bot using environment variable
bot.run(os.getenv("DISCORD_TOKEN"))
