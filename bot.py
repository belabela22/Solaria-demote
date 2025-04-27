import discord
from discord import app_commands
from discord.ext import commands
import os
import threading
import datetime
import json
from flask import Flask

# Flask app for Render keep-alive
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# Files
COOLDOWN_FILE = "cooldowns.json"
PROMOTIONS_FILE = "promotions.json"
DEMOTIONS_FILE = "demotions.json"

# Load/Save Functions
def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def load_cooldowns():
    if not os.path.exists(COOLDOWN_FILE):
        return {}
    with open(COOLDOWN_FILE, "r") as f:
        raw_data = json.load(f)
        cooldowns = {}
        for user, timestamp in raw_data.items():
            cooldowns[user] = datetime.datetime.fromtimestamp(timestamp)
        return cooldowns

def save_cooldowns(cooldowns):
    raw_data = {user: int(time.timestamp()) for user, time in cooldowns.items()}
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(raw_data, f)

# Databases
cooldowns_db = load_cooldowns()
promotions_db = load_json(PROMOTIONS_FILE)
demotions_db = load_json(DEMOTIONS_FILE)

# Discord Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Rank Choices
rank_choices = [
    discord.app_commands.Choice(name=f"EL{i} PR", value=f"EL{i} PR") for i in range(1,10)
] + [
    discord.app_commands.Choice(name=f"EL{i} Medical", value=f"EL{i} Medical") for i in range(1,10)
] + [
    discord.app_commands.Choice(name=f"EL{i} Surgical", value=f"EL{i} Surgical") for i in range(1,10)
] + [
    discord.app_commands.Choice(name=f"EL{i} Nursing", value=f"EL{i} Nursing") for i in range(1,10)
] + [
    discord.app_commands.Choice(name=f"EL{i} Paramedic", value=f"EL{i} Paramedic") for i in range(1,10)
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Promote Command
@bot.tree.command(name="promote", description="Promote a Roblox user with cooldown and save promotion.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank",
    new_rank="New rank",
    cooldown="Cooldown in hours (e.g., 2)"
)
@app_commands.choices(old_rank=rank_choices, new_rank=rank_choices)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: discord.app_commands.Choice[str], new_rank: discord.app_commands.Choice[str], cooldown: float):
    now = datetime.datetime.utcnow()

    if roblox_username in cooldowns_db:
        cooldown_end = cooldowns_db[roblox_username]
        if now < cooldown_end:
            timestamp = int(cooldown_end.timestamp())
            await interaction.response.send_message(
                f"❌ {roblox_username} is still on cooldown! They can be promoted again <t:{timestamp}:R>.", ephemeral=True)
            return

    # Set cooldown
    if cooldown > 0:
        cooldown_end_time = now + datetime.timedelta(hours=cooldown)
        cooldowns_db[roblox_username] = cooldown_end_time
    else:
        cooldowns_db.pop(roblox_username, None)

    save_cooldowns(cooldowns_db)

    # Register promotion
    promotion_id = len(promotions_db) + 1
    promotions_db.append({
        "id": promotion_id,
        "username": roblox_username,
        "old_rank": old_rank.value,
        "new_rank": new_rank.value,
        "time": now.isoformat()
    })
    save_json(PROMOTIONS_FILE, promotions_db)

    # Embed
    embed = discord.Embed(
        title=f"✅ Promotion #{promotion_id} Successful!",
        color=discord.Color.green(),
        timestamp=now
    )
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Old Rank", value=old_rank.value, inline=True)
    embed.add_field(name="New Rank", value=new_rank.value, inline=True)

    if cooldown > 0:
        timestamp = int((now + datetime.timedelta(hours=cooldown)).timestamp())
        embed.add_field(name="Next Promotion Available", value=f"<t:{timestamp}:R>", inline=False)
    else:
        embed.add_field(name="Next Promotion Available", value="Immediate (No cooldown)", inline=False)

    await interaction.response.send_message(embed=embed)

# Promotions Command
@bot.tree.command(name="promotions", description="Check promotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username to search promotions for")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    user_promotions = [promo for promo in promotions_db if promo['username'].lower() == roblox_username.lower()]
    
    if not user_promotions:
        await interaction.response.send_message(f"No promotions found for **{roblox_username}**.", ephemeral=True)
        return

    embed = discord.Embed(title=f"Promotion History for {roblox_username}", color=discord.Color.blue())
    for promo in user_promotions:
        embed.add_field(
            name=f"Promotion #{promo['id']}",
            value=f"**Old Rank:** {promo['old_rank']}\n**New Rank:** {promo['new_rank']}\n**Date:** {promo['time']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# Demote Command
@bot.tree.command(name="demote", description="Demote a Roblox user and optionally delete a promotion.")
@app_commands.describe(
    roblox_username="Roblox username",
    current_rank="Current rank of the user",
    demoted_rank="New demoted rank",
    reason="Reason for demotion",
    delete_promotion_id="Promotion ID to delete (optional)"
)
async def demote(interaction: discord.Interaction, roblox_username: str, current_rank: str, demoted_rank: str, reason: str, delete_promotion_id: int = None):
    now = datetime.datetime.utcnow()

    # Save demotion
    demotions_db.append({
        "username": roblox_username,
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "time": now.isoformat()
    })
    save_json(DEMOTIONS_FILE, demotions_db)

    # Delete promotion if ID given
    deleted = False
    if delete_promotion_id:
        for promo in promotions_db:
            if promo['id'] == delete_promotion_id:
                promotions_db.remove(promo)
                save_json(PROMOTIONS_FILE, promotions_db)
                deleted = True
                break

    # Embed
    embed = discord.Embed(
        title="⚠️ Demotion Executed",
        color=discord.Color.red(),
        timestamp=now
    )
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Current Rank", value=current_rank, inline=True)
    embed.add_field(name="Demoted To", value=demoted_rank, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    if deleted:
        embed.add_field(name="Deleted Promotion ID", value=str(delete_promotion_id), inline=False)

    await interaction.response.send_message(embed=embed)

# Demotions Command
@bot.tree.command(name="demotions", description="Check demotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username to search demotions for")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    user_demotions = [demo for demo in demotions_db if demo['username'].lower() == roblox_username.lower()]
    
    if not user_demotions:
        await interaction.response.send_message(f"No demotions found for **{roblox_username}**.", ephemeral=True)
        return

    embed = discord.Embed(title=f"Demotion History for {roblox_username}", color=discord.Color.dark_red())
    for demo in user_demotions:
        embed.add_field(
            name=f"Demoted on {demo['time']}",
            value=f"**Current Rank:** {demo['current_rank']}\n**Demoted To:** {demo['demoted_rank']}\n**Reason:** {demo['reason']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# Run the Bot
bot.run(os.getenv("DISCORD_TOKEN"))
