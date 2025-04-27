import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import json
import threading
from flask import Flask

# Flask app for Render hosting
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# File paths
PROMOTIONS_FILE = "promotions.json"
DEMOTIONS_FILE = "demotions.json"

# Ensure JSON files exist
def initialize_json_files():
    for file in [PROMOTIONS_FILE, DEMOTIONS_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump([], f)

initialize_json_files()

# Load data from JSON

def load_json(file):
    with open(file, 'r') as f:
        return json.load(f)

# Save data to JSON

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

# Get Roblox avatar
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

# Commands
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="promote", description="Promote a Roblox user.")
@app_commands.describe(robloxuser="Roblox username", old_rank="Old rank", new_rank="New rank", cooldown="Cooldown (e.g., 2h, 12h, 48h)")
async def promote(interaction: discord.Interaction, robloxuser: str, old_rank: str, new_rank: str, cooldown: str):
    promotions = load_json(PROMOTIONS_FILE)
    promotion_id = len(promotions) + 1
    timestamp = datetime.datetime.now().isoformat()

    promotions.append({
        "id": promotion_id,
        "robloxuser": robloxuser,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "cooldown": cooldown,
        "timestamp": timestamp
    })
    save_json(PROMOTIONS_FILE, promotions)

    await interaction.response.send_message(f"✅ **Promotion #{promotion_id}** recorded for **{robloxuser}** from **{old_rank}** to **{new_rank}** with cooldown **{cooldown}**.")

@bot.tree.command(name="promotions", description="View promotion history.")
async def promotions(interaction: discord.Interaction):
    promotions = load_json(PROMOTIONS_FILE)
    if not promotions:
        await interaction.response.send_message("No promotions recorded yet.")
        return

    embed = discord.Embed(title="Promotion History", color=0x00ff00)
    for promo in promotions:
        embed.add_field(
            name=f"Promotion #{promo['id']}",
            value=f"User: {promo['robloxuser']}\nOld Rank: {promo['old_rank']}\nNew Rank: {promo['new_rank']}\nCooldown: {promo['cooldown']}\nTime: {promo['timestamp']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="demote", description="Demote a Roblox user and optionally delete a promotion.")
@app_commands.describe(robloxuser="Roblox username", current_rank="Current rank", demoted_rank="New demoted rank", reason="Reason for demotion", delete_promotion="Promotion number to delete (optional)")
async def demote(interaction: discord.Interaction, robloxuser: str, current_rank: str, demoted_rank: str, reason: str, delete_promotion: int = None):
    if delete_promotion:
        promotions = load_json(PROMOTIONS_FILE)
        promotion_found = False
        for promo in promotions:
            if promo['id'] == delete_promotion:
                promotions.remove(promo)
                save_json(PROMOTIONS_FILE, promotions)
                promotion_found = True
                break
        if not promotion_found:
            await interaction.response.send_message(f"❌ Promotion #{delete_promotion} not found. Demotion canceled.")
            return

    demotions = load_json(DEMOTIONS_FILE)
    timestamp = datetime.datetime.now().isoformat()

    demotions.append({
        "robloxuser": robloxuser,
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "timestamp": timestamp
    })
    save_json(DEMOTIONS_FILE, demotions)

    msg = f"✅ **{robloxuser}** demoted from **{current_rank}** to **{demoted_rank}** for reason: {reason}."
    if delete_promotion:
        msg += f"\nDeleted Promotion #{delete_promotion}."

    await interaction.response.send_message(msg)

@bot.tree.command(name="demotions", description="View demotion history.")
async def demotions(interaction: discord.Interaction):
    demotions = load_json(DEMOTIONS_FILE)
    if not demotions:
        await interaction.response.send_message("No demotions recorded yet.")
        return

    embed = discord.Embed(title="Demotion History", color=0xff0000)
    for demo in demotions:
        embed.add_field(
            name=f"{demo['robloxuser']}",
            value=f"From: {demo['current_rank']} → To: {demo['demoted_rank']}\nReason: {demo['reason']}\nTime: {demo['timestamp']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# Start the bot
bot.run(os.getenv("DISCORD_TOKEN"))
