import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask
from typing import Dict

# Flask app for Render hosting
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

# Promotion database and cooldown tracker
promotion_db: Dict[str, list] = {}
promotion_cooldowns: Dict[str, datetime.datetime] = {}

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

@bot.tree.command(name="promote", description="Promote a Roblox user.")
@app_commands.describe(roblox_username="Roblox username", old_rank="Old rank", new_rank="New rank", cooldown="Cooldown (e.g., 2h, 12h, 2d, no)")
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: str):
    now = datetime.datetime.utcnow()

    # Check if user is still under cooldown
    if roblox_username in promotion_cooldowns:
        cooldown_until = promotion_cooldowns[roblox_username]
        if now < cooldown_until:
            cooldown_unix = int(cooldown_until.timestamp())
            await interaction.response.send_message(
                f"❗ {roblox_username} is still under promotion cooldown! You can promote again <t:{cooldown_unix}:R>.",
                ephemeral=True
            )
            return

    # Parse cooldown input
    duration = None
    if cooldown.endswith('h'):
        hours = int(cooldown[:-1])
        duration = datetime.timedelta(hours=hours)
    elif cooldown.endswith('d'):
        days = int(cooldown[:-1])
        duration = datetime.timedelta(days=days)
    elif cooldown.lower() == "no":
        duration = None
    else:
        await interaction.response.send_message("⚠️ Invalid cooldown format! Use '2h', '2d', or 'no'.", ephemeral=True)
        return

    # Set cooldown if applicable
    cooldown_until = None
    if duration:
        cooldown_until = now + duration
        promotion_cooldowns[roblox_username] = cooldown_until

    # Save promotion info
    avatar_url = await get_roblox_avatar(roblox_username)
    promotion_db.setdefault(roblox_username, []).append({
        "old_rank": old_rank,
        "new_rank": new_rank,
        "promoted_at": now.isoformat(),
        "cooldown_until": cooldown_until.isoformat() if cooldown_until else "None"
    })

    # Create embed message
    embed = discord.Embed(title="Promotion Logged!", color=discord.Color.green())
    embed.add_field(name="Roblox Username", value=roblox_username, inline=False)
    embed.add_field(name="Old Rank", value=old_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)
    if cooldown_until:
        cooldown_unix = int(cooldown_until.timestamp())
        embed.add_field(name="Cooldown Ends", value=f"<t:{cooldown_unix}:R>", inline=False)
    else:
        embed.add_field(name="Cooldown Ends", value="No cooldown (instant promotion)", inline=False)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    await interaction.response.send_message(embed=embed)

# Run bot
bot.run(os.getenv("DISCORD_TOKEN"))
