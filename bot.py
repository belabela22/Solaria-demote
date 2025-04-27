import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import datetime
import threading
from flask import Flask

# --- Flask setup for Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# --- Files ---
PROMOTION_FILE = "promotions.json"
DEMOTION_FILE = "demotions.json"
COOLDOWN_FILE = "cooldowns.json"

def load_json(filename, default):
    if not os.path.exists(filename):
        return default
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

promotions_db = load_json(PROMOTION_FILE, {})
demotions_db = load_json(DEMOTION_FILE, {})
cooldowns_db = load_json(COOLDOWN_FILE, {})

def save_all():
    save_json(PROMOTION_FILE, promotions_db)
    save_json(DEMOTION_FILE, demotions_db)
    save_json(COOLDOWN_FILE, cooldowns_db)

# --- Discord Bot ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Rank Choices ---
ranks = [
    "EL1 PR", "EL2 PR", "EL3 PR", "EL4 PR", "EL5 PR", "EL6 PR", "EL7 PR", "EL8 PR", "EL9 PR",
    "EL1 Medical", "EL2 Medical", "EL3 Medical", "EL4 Medical", "EL5 Medical", "EL6 Medical", "EL7 Medical", "EL8 Medical", "EL9 Medical",
    "EL1 Surgical", "EL2 Surgical", "EL3 Surgical", "EL4 Surgical", "EL5 Surgical", "EL6 Surgical", "EL7 Surgical", "EL8 Surgical", "EL9 Surgical",
    "EL1 Nursing", "EL2 Nursing", "EL3 Nursing", "EL4 Nursing", "EL5 Nursing", "EL6 Nursing", "EL7 Nursing", "EL8 Nursing", "EL9 Nursing",
    "EL1 Paramedic", "EL2 Paramedic", "EL3 Paramedic", "EL4 Paramedic", "EL5 Paramedic", "EL6 Paramedic", "EL7 Paramedic", "EL8 Paramedic", "EL9 Paramedic"
]

rank_choices = [app_commands.Choice(name=rank, value=rank) for rank in ranks]

# --- Bot Events ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot connected as {bot.user}")

# --- Promote Command ---
@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="User's old rank",
    new_rank="User's new rank",
    cooldown="Cooldown in hours"
)
@app_commands.choices(old_rank=rank_choices, new_rank=rank_choices)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: app_commands.Choice[str], new_rank: app_commands.Choice[str], cooldown: float):

    now = datetime.datetime.utcnow()
    user = roblox_username.lower()

    if user in cooldowns_db:
        cooldown_end = datetime.datetime.fromtimestamp(cooldowns_db[user])
        if now < cooldown_end:
            await interaction.response.send_message(f"❌ {roblox_username} is on cooldown until <t:{int(cooldown_end.timestamp())}:R>.", ephemeral=True)
            return

    # Set cooldown
    if cooldown > 0:
        cooldown_end = now + datetime.timedelta(hours=cooldown)
        cooldowns_db[user] = int(cooldown_end.timestamp())
    else:
        cooldowns_db.pop(user, None)

    # Promotion Registration
    promotions_db.setdefault(user, [])
    promo_number = len(promotions_db[user]) + 1
    promotions_db[user].append({
        "number": promo_number,
        "old_rank": old_rank.value,
        "new_rank": new_rank.value,
        "time": now.isoformat()
    })

    save_all()

    # Send embed
    embed = discord.Embed(title=f"✅ Promotion #{promo_number}", color=discord.Color.green(), timestamp=now)
    embed.add_field(name="Username", value=roblox_username, inline=True)
    embed.add_field(name="Old Rank", value=old_rank.value, inline=True)
    embed.add_field(name="New Rank", value=new_rank.value, inline=True)
    await interaction.response.send_message(embed=embed)

# --- Demote Command ---
@bot.tree.command(name="demote", description="Demote a Roblox user")
@app_commands.describe(
    roblox_username="Roblox username",
    current_rank="User's current rank",
    demoted_rank="User's new (lower) rank",
    reason="Reason for demotion"
)
@app_commands.choices(current_rank=rank_choices, demoted_rank=rank_choices)
async def demote(interaction: discord.Interaction, roblox_username: str, current_rank: app_commands.Choice[str], demoted_rank: app_commands.Choice[str], reason: str):

    now = datetime.datetime.utcnow()
    user = roblox_username.lower()

    demotions_db.setdefault(user, [])
    demo_number = len(demotions_db[user]) + 1
    demotions_db[user].append({
        "number": demo_number,
        "current_rank": current_rank.value,
        "demoted_rank": demoted_rank.value,
        "reason": reason,
        "time": now.isoformat()
    })

    save_all()

    embed = discord.Embed(title=f"❌ Demotion #{demo_number}", color=discord.Color.red(), timestamp=now)
    embed.add_field(name="Username", value=roblox_username, inline=True)
    embed.add_field(name="Current Rank", value=current_rank.value, inline=True)
    embed.add_field(name="Demoted To", value=demoted_rank.value, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.response.send_message(embed=embed)

# --- Promotions History ---
@bot.tree.command(name="promotions", description="View promotions of a user")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    user = roblox_username.lower()
    promos = promotions_db.get(user, [])

    if not promos:
        await interaction.response.send_message(f"❌ No promotions found for {roblox_username}.", ephemeral=True)
        return

    embed = discord.Embed(title=f"Promotions of {roblox_username}", color=discord.Color.blue())
    for p in promos:
        time = datetime.datetime.fromisoformat(p["time"])
        embed.add_field(name=f"Promotion #{p['number']}", value=f"{p['old_rank']} ➔ {p['new_rank']} at <t:{int(time.timestamp())}:f>", inline=False)

    await interaction.response.send_message(embed=embed)

# --- Demotions History ---
@bot.tree.command(name="demotions", description="View demotions of a user")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    user = roblox_username.lower()
    demos = demotions_db.get(user, [])

    if not demos:
        await interaction.response.send_message(f"❌ No demotions found for {roblox_username}.", ephemeral=True)
        return

    embed = discord.Embed(title=f"Demotions of {roblox_username}", color=discord.Color.purple())
    for d in demos:
        time = datetime.datetime.fromisoformat(d["time"])
        embed.add_field(name=f"Demotion #{d['number']}", value=f"{d['current_rank']} ➔ {d['demoted_rank']} | Reason: {d['reason']} at <t:{int(time.timestamp())}:f>", inline=False)

    await interaction.response.send_message(embed=embed)

# --- Delete Promotion by Number ---
@bot.tree.command(name="delete_promotion", description="Delete a promotion record")
@app_commands.describe(
    roblox_username="Roblox username",
    promotion_number="Promotion number to delete"
)
async def delete_promotion(interaction: discord.Interaction, roblox_username: str, promotion_number: int):
    user = roblox_username.lower()
    promos = promotions_db.get(user, [])

    promo = next((p for p in promos if p["number"] == promotion_number), None)
    if not promo:
        await interaction.response.send_message(f"❌ Promotion #{promotion_number} not found for {roblox_username}.", ephemeral=True)
        return

    promotions_db[user].remove(promo)
    save_all()

    embed = discord.Embed(
        title="✅ Promotion Deleted",
        description=f"Promotion #{promotion_number} for {roblox_username} has been deleted.",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

# --- Run the Bot ---
bot.run(os.getenv("DISCORD_TOKEN"))
