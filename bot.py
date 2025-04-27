import discord
from discord import app_commands
from discord.ext import commands
import os
import threading
import datetime
import json
from flask import Flask

# Flask for Render
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# Promotion and cooldown database
PROMOTION_FILE = "promotions.json"
COOLDOWN_FILE = "cooldowns.json"

# Load promotions
def load_promotions():
    if not os.path.exists(PROMOTION_FILE):
        return []
    with open(PROMOTION_FILE, "r") as f:
        return json.load(f)

def save_promotions(promotions):
    with open(PROMOTION_FILE, "w") as f:
        json.dump(promotions, f, indent=4)

# Load cooldowns
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
        json.dump(raw_data, f, indent=4)

promotions_db = load_promotions()
cooldowns_db = load_cooldowns()

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Promote Command
@bot.tree.command(name="promote", description="Promote a Roblox user with a cooldown.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank of the user",
    new_rank="New rank of the user",
    cooldown="Cooldown in hours (example: 2 for 2 hours)"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: float):
    now = datetime.datetime.utcnow()

    if roblox_username in cooldowns_db:
        cooldown_end = cooldowns_db[roblox_username]
        if now < cooldown_end:
            timestamp = int(cooldown_end.timestamp())
            await interaction.response.send_message(
                f"❌ {roblox_username} is still on cooldown! They can be promoted again <t:{timestamp}:R>.", ephemeral=True)
            return

    # Set new cooldown
    if cooldown > 0:
        cooldown_end_time = now + datetime.timedelta(hours=cooldown)
        cooldowns_db[roblox_username] = cooldown_end_time
    else:
        cooldowns_db.pop(roblox_username, None)

    save_cooldowns(cooldowns_db)

    # Assign new promotion ID
    promotion_id = len(promotions_db) + 1
    promotions_db.append({
        "id": promotion_id,
        "username": roblox_username,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "time": now.isoformat()
    })
    save_promotions(promotions_db)

    # Embed response
    embed = discord.Embed(
        title=f"✅ Promotion #{promotion_id} Successful!",
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

# Promotions Command
@bot.tree.command(name="promotions", description="Check promotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    user_promotions = [p for p in promotions_db if p["username"].lower() == roblox_username.lower()]

    if not user_promotions:
        await interaction.response.send_message(f"No promotions found for **{roblox_username}**.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Promotion History for {roblox_username}",
        color=discord.Color.blue()
    )
    for promo in user_promotions:
        time = datetime.datetime.fromisoformat(promo["time"])
        embed.add_field(
            name=f"Promotion #{promo['id']}",
            value=f"Old Rank: {promo['old_rank']} ➔ New Rank: {promo['new_rank']} at <t:{int(time.timestamp())}:f>",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Demote Command
@bot.tree.command(name="demote", description="Demote a Roblox user by deleting a promotion.")
@app_commands.describe(
    promotion_id="Promotion ID to delete (number)",
    reason="Reason for demotion"
)
async def demote(interaction: discord.Interaction, promotion_id: int, reason: str):
    global promotions_db
    found = None

    for promo in promotions_db:
        if promo["id"] == promotion_id:
            found = promo
            break

    if not found:
        await interaction.response.send_message(f"❌ Promotion with ID #{promotion_id} not found.", ephemeral=True)
        return

    promotions_db.remove(found)
    save_promotions(promotions_db)

    embed = discord.Embed(
        title=f"❌ Demotion Successful",
        description=f"Promotion #{promotion_id} has been removed.\n**Reason:** {reason}",
        color=discord.Color.red()
    )
    embed.add_field(name="Roblox Username", value=found["username"], inline=True)
    embed.add_field(name="Old Rank", value=found["old_rank"], inline=True)
    embed.add_field(name="New Rank", value=found["new_rank"], inline=True)

    await interaction.response.send_message(embed=embed)

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
