import discord
from discord import app_commands
from discord.ext import commands
import os
import threading
import datetime
import json
from flask import Flask

# Flask setup for Render hosting
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# Files for storing promotions and cooldowns
PROMOTION_FILE = "promotions.json"
COOLDOWN_FILE = "cooldowns.json"

# Load promotions
def load_promotions():
    if not os.path.exists(PROMOTION_FILE):
        return []
    with open(PROMOTION_FILE, "r") as f:
        return json.load(f)

# Save promotions
def save_promotions(promotions):
    with open(PROMOTION_FILE, "w") as f:
        json.dump(promotions, f, indent=4)

# Load cooldowns
def load_cooldowns():
    if not os.path.exists(COOLDOWN_FILE):
        return {}
    with open(COOLDOWN_FILE, "r") as f:
        raw_data = json.load(f)
        cooldowns = {user: datetime.datetime.fromtimestamp(timestamp) for user, timestamp in raw_data.items()}
        return cooldowns

# Save cooldowns
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
        print(f"Failed to sync commands: {e}")

# Promote Command
@bot.tree.command(name="promote", description="Promote a Roblox user with cooldown management.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank",
    new_rank="New rank",
    cooldown="Cooldown time in hours (set 0 for no cooldown)"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: float):
    now = datetime.datetime.utcnow()

    # Check cooldown
    if roblox_username in cooldowns_db and now < cooldowns_db[roblox_username]:
        cooldown_end = cooldowns_db[roblox_username]
        await interaction.response.send_message(
            f"❌ {roblox_username} is still on cooldown! Try again <t:{int(cooldown_end.timestamp())}:R>.",
            ephemeral=True
        )
        return

    # Update cooldown
    if cooldown > 0:
        cooldown_end = now + datetime.timedelta(hours=cooldown)
        cooldowns_db[roblox_username] = cooldown_end
    else:
        cooldowns_db.pop(roblox_username, None)
    save_cooldowns(cooldowns_db)

    # Save promotion
    promotion_id = len(promotions_db) + 1
    promotions_db.append({
        "id": promotion_id,
        "username": roblox_username,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "time": now.isoformat()
    })
    save_promotions(promotions_db)

    # Respond
    embed = discord.Embed(
        title=f"✅ Promotion #{promotion_id} Successful!",
        color=discord.Color.green(),
        timestamp=now
    )
    embed.add_field(name="Username", value=roblox_username, inline=True)
    embed.add_field(name="Old Rank", value=old_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)

    if cooldown > 0:
        embed.add_field(name="Next Promotion Available", value=f"<t:{int(cooldown_end.timestamp())}:R>", inline=False)
    else:
        embed.add_field(name="Next Promotion Available", value="No cooldown", inline=False)

    await interaction.response.send_message(embed=embed)

# Promotions Command
@bot.tree.command(name="promotions", description="See a user's promotion history.")
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

    for idx, promo in enumerate(user_promotions, 1):
        time = datetime.datetime.fromisoformat(promo["time"])
        embed.add_field(
            name=f"Promotion {idx}: (ID #{promo['id']})",
            value=f"**{promo['old_rank']} ➔ {promo['new_rank']}** at <t:{int(time.timestamp())}:f>",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Demotions Command (alias for promotions)
@bot.tree.command(name="demotions", description="(Same as promotions) See user's full promotion history.")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    await promotions(interaction, roblox_username)

# Demote Command
@bot.tree.command(name="demote", description="Delete a specific promotion of a Roblox user.")
@app_commands.describe(
    roblox_username="Roblox username",
    promotion_number="Promotion number to delete (from promotions history)",
    reason="Reason for demotion"
)
async def demote(interaction: discord.Interaction, roblox_username: str, promotion_number: int, reason: str):
    global promotions_db
    user_promotions = [p for p in promotions_db if p["username"].lower() == roblox_username.lower()]

    if not user_promotions:
        await interaction.response.send_message(f"No promotions found for **{roblox_username}**.", ephemeral=True)
        return

    if promotion_number < 1 or promotion_number > len(user_promotions):
        await interaction.response.send_message(f"Invalid promotion number. Choose between 1 and {len(user_promotions)}.", ephemeral=True)
        return

    to_remove = user_promotions[promotion_number - 1]
    promotions_db.remove(to_remove)
    save_promotions(promotions_db)

    embed = discord.Embed(
        title="❌ Demotion Successful",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Username", value=roblox_username, inline=True)
    embed.add_field(name="Old Rank", value=to_remove["old_rank"], inline=True)
    embed.add_field(name="New Rank", value=to_remove["new_rank"], inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)

    await interaction.response.send_message(embed=embed)

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
