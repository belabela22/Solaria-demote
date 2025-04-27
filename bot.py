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

PROMOTION_FILE = "promotions.json"
DEMOTION_FILE = "demotions.json"
COOLDOWN_FILE = "cooldowns.json"

# Helpers for file operations
def load_json(filename, default):
    if not os.path.exists(filename):
        return default
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# Load databases
promotions_db = load_json(PROMOTION_FILE, {})  # per user
cooldowns_db = load_json(COOLDOWN_FILE, {})
demotions_db = load_json(DEMOTION_FILE, {})

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

RANK_CHOICES = [
    "EL1 PR", "EL2 PR", "EL3 PR", "EL4 PR", "EL5 PR", "EL6 PR", "EL7 PR", "EL8 PR", "EL9 PR",
    "EL1 Medical", "EL2 Medical", "EL3 Medical", "EL4 Medical", "EL5 Medical", "EL6 Medical", "EL7 Medical", "EL8 Medical", "EL9 Medical",
    "EL1 Surgical", "EL2 Surgical", "EL3 Surgical", "EL4 Surgical", "EL5 Surgical", "EL6 Surgical", "EL7 Surgical", "EL8 Surgical", "EL9 Surgical",
    "EL1 Nursing", "EL2 Nursing", "EL3 Nursing", "EL4 Nursing", "EL5 Nursing", "EL6 Nursing", "EL7 Nursing", "EL8 Nursing", "EL9 Nursing",
    "EL1 Paramedic", "EL2 Paramedic", "EL3 Paramedic", "EL4 Paramedic", "EL5 Paramedic", "EL6 Paramedic", "EL7 Paramedic", "EL8 Paramedic", "EL9 Paramedic"
]

# Dropdown autocomplete
def rank_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=rank, value=rank) for rank in RANK_CHOICES if current.lower() in rank.lower()][:25]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Promote Command
@bot.tree.command(name="promote", description="Promote a Roblox user.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank",
    new_rank="New rank",
    cooldown="Cooldown in hours"
)
@app_commands.autocomplete(old_rank=rank_autocomplete, new_rank=rank_autocomplete)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: float):
    now = datetime.datetime.utcnow()
    
    # Check cooldown
    if roblox_username in cooldowns_db:
        cooldown_end = datetime.datetime.fromtimestamp(cooldowns_db[roblox_username])
        if now < cooldown_end:
            await interaction.response.send_message(
                f"❌ {roblox_username} is still on cooldown! Wait until <t:{int(cooldown_end.timestamp())}:R>.", ephemeral=True)
            return
    
    # Cooldown update
    if cooldown > 0:
        cooldowns_db[roblox_username] = (now + datetime.timedelta(hours=cooldown)).timestamp()
    else:
        cooldowns_db.pop(roblox_username, None)
    save_json(COOLDOWN_FILE, cooldowns_db)

    # Promotions update
    if roblox_username not in promotions_db:
        promotions_db[roblox_username] = []
    promotion_number = len(promotions_db[roblox_username]) + 1
    promotions_db[roblox_username].append({
        "promotion_number": promotion_number,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "time": now.isoformat()
    })
    save_json(PROMOTION_FILE, promotions_db)

    # Response
    embed = discord.Embed(
        title=f"✅ Promotion #{promotion_number} Successful!",
        color=discord.Color.green(),
        timestamp=now
    )
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Old Rank", value=old_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)
    embed.add_field(name="Promotion #", value=str(promotion_number), inline=False)
    await interaction.response.send_message(embed=embed)

# Promotions History Command
@bot.tree.command(name="promotions", description="View promotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    user_promos = promotions_db.get(roblox_username, [])
    if not user_promos:
        await interaction.response.send_message(f"No promotions found for **{roblox_username}**.", ephemeral=True)
        return

    embed = discord.Embed(title=f"Promotion History for {roblox_username}", color=discord.Color.blue())
    for promo in user_promos:
        time = datetime.datetime.fromisoformat(promo["time"])
        embed.add_field(
            name=f"Promotion #{promo['promotion_number']}",
            value=f"{promo['old_rank']} ➔ {promo['new_rank']} at <t:{int(time.timestamp())}:f>",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# Demote Command
@bot.tree.command(name="demote", description="Demote a Roblox user by promotion number.")
@app_commands.describe(
    roblox_username="Roblox username",
    promotion_number="Promotion number to demote",
    current_rank="Current rank",
    demoted_rank="Demoted to",
    reason="Reason for demotion"
)
async def demote(interaction: discord.Interaction, roblox_username: str, promotion_number: int, current_rank: str, demoted_rank: str, reason: str):
    now = datetime.datetime.utcnow()

    if roblox_username not in promotions_db:
        await interaction.response.send_message(f"❌ No promotions found for {roblox_username}.", ephemeral=True)
        return

    promo_list = promotions_db[roblox_username]
    found = None
    for promo in promo_list:
        if promo["promotion_number"] == promotion_number:
            found = promo
            break

    if not found:
        await interaction.response.send_message(f"❌ Promotion #{promotion_number} not found for {roblox_username}.", ephemeral=True)
        return

    promo_list.remove(found)
    save_json(PROMOTION_FILE, promotions_db)

    # Save to demotions
    if roblox_username not in demotions_db:
        demotions_db[roblox_username] = []
    demotions_db[roblox_username].append({
        "promotion_number": promotion_number,
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "time": now.isoformat()
    })
    save_json(DEMOTION_FILE, demotions_db)

    embed = discord.Embed(
        title=f"❌ Demotion Successful",
        description=f"Promotion #{promotion_number} removed.",
        color=discord.Color.red(),
        timestamp=now
    )
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Current Rank", value=current_rank, inline=True)
    embed.add_field(name="Demoted Rank", value=demoted_rank, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.response.send_message(embed=embed)

# Demotions History Command
@bot.tree.command(name="demotions", description="View demotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    user_demotes = demotions_db.get(roblox_username, [])
    if not user_demotes:
        await interaction.response.send_message(f"No demotions found for **{roblox_username}**.", ephemeral=True)
        return

    embed = discord.Embed(title=f"Demotion History for {roblox_username}", color=discord.Color.dark_red())
    for demo in user_demotes:
        time = datetime.datetime.fromisoformat(demo["time"])
        embed.add_field(
            name=f"Demotion #{demo['promotion_number']}",
            value=f"From {demo['current_rank']} to {demo['demoted_rank']} | Reason: {demo['reason']} at <t:{int(time.timestamp())}:f>",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# Help Command
@bot.tree.command(name="help", description="View all available commands.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Command List",
        description="Here are all available commands:",
        color=discord.Color.teal()
    )

    embed.add_field(
        name="/promote",
        value="Promote a Roblox user, set old rank, new rank, and cooldown.",
        inline=False
    )
    embed.add_field(
        name="/promotions",
        value="View promotion history of a Roblox user.",
        inline=False
    )
    embed.add_field(
        name="/demote",
        value="Demote a user by deleting a promotion, recording current rank, demoted rank, and reason.",
        inline=False
    )
    embed.add_field(
        name="/demotions",
        value="View demotion history of a Roblox user.",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
