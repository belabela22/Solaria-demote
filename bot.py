import discord
from discord import app_commands
from discord.ext import commands
import os
import threading
import datetime
import json
from flask import Flask

# Web server for Render
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
PROMOTION_FILE = "promotions.json"
DEMOTION_FILE = "demotions.json"

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# Load Data
cooldowns = load_json(COOLDOWN_FILE)
promotions = load_json(PROMOTION_FILE)
demotions = load_json(DEMOTION_FILE)

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

promotion_counter = max([int(k) for k in promotions.keys()]) + 1 if promotions else 1

# Choices for ranks
rank_choices = [
    discord.app_commands.Choice(name=f"PR - EL{i} PR", value=f"EL{i} PR") for i in range(1, 10)
] + [
    discord.app_commands.Choice(name=f"Medical - EL{i} Medical", value=f"EL{i} Medical") for i in range(1, 10)
] + [
    discord.app_commands.Choice(name=f"Surgical - EL{i} Surgical", value=f"EL{i} Surgical") for i in range(1, 10)
] + [
    discord.app_commands.Choice(name=f"Nursing - EL{i} Nursing", value=f"EL{i} Nursing") for i in range(1, 10)
] + [
    discord.app_commands.Choice(name=f"Paramedic - EL{i} Paramedic", value=f"EL{i} Paramedic") for i in range(1, 10)
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# /promote command
@bot.tree.command(name="promote", description="Promote a Roblox user with cooldown and history.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank (choose)",
    new_rank="New rank (choose)",
    cooldown="Cooldown in hours (example: 2)"
)
@app_commands.choices(old_rank=rank_choices, new_rank=rank_choices)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: discord.app_commands.Choice[str], new_rank: discord.app_commands.Choice[str], cooldown: float):
    global promotion_counter

    now = datetime.datetime.utcnow()

    # Cooldown check
    if roblox_username in cooldowns:
        cooldown_end = datetime.datetime.fromtimestamp(cooldowns[roblox_username])
        if now < cooldown_end:
            timestamp = int(cooldown_end.timestamp())
            await interaction.response.send_message(f"❌ {roblox_username} is still on cooldown! Try again <t:{timestamp}:R>.", ephemeral=True)
            return

    # Save cooldown
    if cooldown > 0:
        cooldown_end = now + datetime.timedelta(hours=cooldown)
        cooldowns[roblox_username] = int(cooldown_end.timestamp())
    else:
        cooldowns.pop(roblox_username, None)
    save_json(COOLDOWN_FILE, cooldowns)

    # Save promotion
    promotions[str(promotion_counter)] = {
        "roblox_username": roblox_username,
        "old_rank": old_rank.value,
        "new_rank": new_rank.value,
        "timestamp": now.isoformat(),
        "by": interaction.user.id
    }
    save_json(PROMOTION_FILE, promotions)

    # Embed
    embed = discord.Embed(
        title="✅ Promotion Successful!",
        color=discord.Color.green(),
        timestamp=now
    )
    embed.add_field(name="Promotion ID", value=promotion_counter, inline=True)
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Old Rank", value=old_rank.value, inline=True)
    embed.add_field(name="New Rank", value=new_rank.value, inline=True)
    if cooldown > 0:
        embed.add_field(name="Next Promotion Available", value=f"<t:{int(cooldown_end.timestamp())}:R>", inline=False)
    else:
        embed.add_field(name="Next Promotion Available", value="Immediate (No cooldown)", inline=False)

    promotion_counter += 1
    await interaction.response.send_message(embed=embed)

# /promotions command
@bot.tree.command(name="promotions", description="View promotion history of a Roblox user.")
@app_commands.describe(roblox_username="Roblox username to check history")
async def promotions_cmd(interaction: discord.Interaction, roblox_username: str):
    user_promotions = [f"ID {pid}: {p['old_rank']} ➔ {p['new_rank']} <t:{int(datetime.datetime.fromisoformat(p['timestamp']).timestamp())}:R>" for pid, p in promotions.items() if p["roblox_username"].lower() == roblox_username.lower()]

    if not user_promotions:
        await interaction.response.send_message(f"No promotions found for {roblox_username}.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Promotion History for {roblox_username}",
        description="\n".join(user_promotions),
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

# /demote command
@bot.tree.command(name="demote", description="Demote a Roblox user and optionally delete promotion record.")
@app_commands.describe(
    roblox_username="Roblox username",
    current_rank="Current rank (choose)",
    demoted_rank="Demoted rank (choose)",
    reason="Reason for demotion",
    promotion_id="Promotion ID to delete (optional)"
)
@app_commands.choices(current_rank=rank_choices, demoted_rank=rank_choices)
async def demote(interaction: discord.Interaction, roblox_username: str, current_rank: discord.app_commands.Choice[str], demoted_rank: discord.app_commands.Choice[str], reason: str, promotion_id: int = None):
    now = datetime.datetime.utcnow()

    # Save demotion
    demotions[str(len(demotions)+1)] = {
        "roblox_username": roblox_username,
        "current_rank": current_rank.value,
        "demoted_rank": demoted_rank.value,
        "reason": reason,
        "timestamp": now.isoformat(),
        "by": interaction.user.id
    }
    save_json(DEMOTION_FILE, demotions)

    if promotion_id and str(promotion_id) in promotions:
        promotions.pop(str(promotion_id))
        save_json(PROMOTION_FILE, promotions)
        promo_deleted = f"Promotion ID {promotion_id} deleted."
    else:
        promo_deleted = "No promotion deleted."

    # Embed
    embed = discord.Embed(
        title="❌ Demotion Recorded",
        color=discord.Color.red(),
        timestamp=now
    )
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="From Rank", value=current_rank.value, inline=True)
    embed.add_field(name="To Rank", value=demoted_rank.value, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Promotion Deletion", value=promo_deleted, inline=False)

    await interaction.response.send_message(embed=embed)

# /demotions command
@bot.tree.command(name="demotions", description="View demotion history.")
async def demotions_cmd(interaction: discord.Interaction):
    if not demotions:
        await interaction.response.send_message("No demotions recorded yet.", ephemeral=True)
        return

    demotion_list = [f"{d['roblox_username']}: {d['current_rank']} ➔ {d['demoted_rank']} (Reason: {d['reason']}) <t:{int(datetime.datetime.fromisoformat(d['timestamp']).timestamp())}:R>" for d in demotions.values()]

    embed = discord.Embed(
        title="Demotion History",
        description="\n".join(demotion_list),
        color=discord.Color.dark_red()
    )
    await interaction.response.send_message(embed=embed)

# Run bot
bot.run(os.getenv("DISCORD_TOKEN"))
