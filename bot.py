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

# Files
COOLDOWN_FILE = "cooldowns.json"
HISTORY_FILE = "promotion_history.json"
DEMOTION_HISTORY_FILE = "demotion_history.json"

def load_json(file, default_data):
    if not os.path.exists(file):
        return default_data
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

promotion_db = load_json(COOLDOWN_FILE, {})
promotion_history = load_json(HISTORY_FILE, [])
demotion_history = load_json(DEMOTION_HISTORY_FILE, [])

def save_cooldowns():
    raw_data = {user: int(time.timestamp()) for user, time in promotion_db.items()}
    save_json(COOLDOWN_FILE, raw_data)

def save_history():
    save_json(HISTORY_FILE, promotion_history)

def save_demotion_history():
    save_json(DEMOTION_HISTORY_FILE, demotion_history)

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

# Slash command to promote
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

    save_cooldowns()

    # Record promotion to history
    promotion_history.append({
        "roblox_username": roblox_username,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "time": now.isoformat()
    })
    save_history()

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

# Slash command to view promotions
@bot.tree.command(name="promotions", description="View promotion history of all users.")
async def promotions(interaction: discord.Interaction):
    if not promotion_history:
        await interaction.response.send_message("No promotions have been recorded yet.", ephemeral=True)
        return

    embed = discord.Embed(
        title="Promotion History",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )

    for idx, promo in enumerate(promotion_history, 1):
        time_fmt = datetime.datetime.fromisoformat(promo["time"]).strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(
            name=f"Promotion #{idx}",
            value=f"User: {promo['roblox_username']}\nOld: {promo['old_rank']} → New: {promo['new_rank']}\nTime: {time_fmt}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Slash command to demote
@bot.tree.command(name="demote", description="Demote a Roblox user with a reason and delete promotion.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank of the user",
    new_rank="New demoted rank of the user",
    reason="Reason for the demotion",
    promotion_id="ID of the promotion to delete"
)
async def demote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, reason: str, promotion_id: int = None):
    now = datetime.datetime.utcnow()

    # Record demotion to history
    demotion_history.append({
        "roblox_username": roblox_username,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "reason": reason,
        "time": now.isoformat()
    })
    save_demotion_history()

    if promotion_id:
        # Delete promotion by ID (remove from history)
        if 0 < promotion_id <= len(promotion_history):
            deleted_promotion = promotion_history.pop(promotion_id - 1)
            save_history()
            await interaction.response.send_message(
                f"❌ Promotion #{promotion_id} deleted successfully. {deleted_promotion['roblox_username']} was promoted from {deleted_promotion['old_rank']} to {deleted_promotion['new_rank']}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Invalid promotion ID. Cannot delete.", ephemeral=True)
            return
    else:
        await interaction.response.send_message(f"✅ {roblox_username} has been demoted from {old_rank} to {new_rank} for reason: {reason}", ephemeral=True)

# Slash command to view demotions
@bot.tree.command(name="demotions", description="View demotion history of all users.")
async def demotions(interaction: discord.Interaction):
    if not demotion_history:
        await interaction.response.send_message("No demotions have been recorded yet.", ephemeral=True)
        return

    embed = discord.Embed(
        title="Demotion History",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )

    for idx, demote in enumerate(demotion_history, 1):
        time_fmt = datetime.datetime.fromisoformat(demote["time"]).strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(
            name=f"Demotion #{idx}",
            value=f"User: {demote['roblox_username']}\nOld: {demote['old_rank']} → New: {demote['new_rank']}\nReason: {demote['reason']}\nTime: {time_fmt}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
