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

# Cooldown system
COOLDOWN_FILE = "cooldowns.json"

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

promotion_db = load_cooldowns()

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

# Slash command
@bot.tree.command(name="promote", description="Promote a Roblox user with a cooldown.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank of the user",
    new_rank="New rank of the user",
    cooldown="Cooldown in hours (example: 2 for 2 hours)"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: float):
    now = datetime.datetime.utcnow()

    if roblox_username in promotion_db:
        cooldown_end = promotion_db[roblox_username]
        if now < cooldown_end:
            timestamp = int(cooldown_end.timestamp())
            await interaction.response.send_message(
                f"❌ {roblox_username} is still on cooldown! They can be promoted again <t:{timestamp}:R>.", ephemeral=True)
            return

    # Set new cooldown
    if cooldown > 0:
        cooldown_end_time = now + datetime.timedelta(hours=cooldown)
        promotion_db[roblox_username] = cooldown_end_time
    else:
        promotion_db.pop(roblox_username, None)

    save_cooldowns(promotion_db)

    # Embed response
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

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
