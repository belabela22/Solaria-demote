import discord
from discord import app_commands
from discord.ext import commands
import os
import threading
import datetime
import json
from flask import Flask

# ——— Flask keep-alive for Render ———
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

# ——— File paths ———
PROMOTION_FILE = "promotions.json"
DEMOTION_FILE = "demotions.json"
COOLDOWN_FILE  = "cooldowns.json"

# ——— JSON helpers ———
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# ——— Load databases ———
promotions_db = load_json(PROMOTION_FILE, {})   # { username: [ {promotion_number, old_rank, new_rank, time_iso}, ... ] }
demotions_db  = load_json(DEMOTION_FILE, {})    # { username: [ {promotion_number, current_rank, demoted_rank, reason, time_iso}, ... ] }
cooldowns_db  = load_json(COOLDOWN_FILE,  {})   # { username: timestamp_int }

# ——— Discord bot setup ———
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ——— Rank list for autocomplete ———
CATEGORIES = {
    "PR":      list(range(1,10)),
    "Medical": list(range(1,10)),
    "Surgical":list(range(1,10)),
    "Nursing": list(range(1,10)),
    "Paramedic": list(range(1,10))
}
RANK_CHOICES = [
    app_commands.Choice(name=f"{cat} - EL{i} {cat}", value=f"EL{i} {cat}")
    for cat, nums in CATEGORIES.items() for i in nums
]

async def rank_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    return [
        choice for choice in RANK_CHOICES
        if current in choice.name.lower()
    ][:25]

# ——— on_ready ———
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")

# ——— /promote ———
@bot.tree.command(name="promote", description="Promote a Roblox user with cooldown and history.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank (choose)",
    new_rank="New rank (choose)",
    cooldown="Cooldown in hours (0 for none)"
)
@app_commands.autocomplete(old_rank=rank_autocomplete, new_rank=rank_autocomplete)
async def promote(
    interaction: discord.Interaction,
    roblox_username: str,
    old_rank: str,
    new_rank: str,
    cooldown: float
):
    now = datetime.datetime.utcnow()
    now_ts = int(now.timestamp())

    # Cooldown check
    cd = cooldowns_db.get(roblox_username)
    if cd and now_ts < cd:
        await interaction.response.send_message(
            f"❌ {roblox_username} still on cooldown! Try again <t:{cd}:R>.",
            ephemeral=True
        )
        return

    # Update cooldown
    if cooldown > 0:
        cooldowns_db[roblox_username] = now_ts + int(cooldown*3600)
    else:
        cooldowns_db.pop(roblox_username, None)
    save_json(COOLDOWN_FILE, cooldowns_db)

    # Record promotion
    user_list = promotions_db.setdefault(roblox_username, [])
    promo_num = len(user_list) + 1
    user_list.append({
        "promotion_number": promo_num,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "time": now.isoformat()
    })
    save_json(PROMOTION_FILE, promotions_db)

    # Respond
    embed = discord.Embed(
        title=f"✅ Promotion #{promo_num} Recorded!",
        color=discord.Color.green(),
        timestamp=now
    )
    embed.add_field(name="User",      value=roblox_username, inline=True)
    embed.add_field(name="Old Rank",  value=old_rank,         inline=True)
    embed.add_field(name="New Rank",  value=new_rank,         inline=True)
    embed.add_field(name="Promo #",   value=str(promo_num),   inline=True)
    if cooldown > 0:
        cd_end = cooldowns_db[roblox_username]
        embed.add_field(
            name="Next Available",
            value=f"<t:{cd_end}:R>",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# ——— /promotions ———
@bot.tree.command(name="promotions", description="Show promotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(
    interaction: discord.Interaction,
    roblox_username: str
):
    user_list = promotions_db.get(roblox_username, [])
    if not user_list:
        await interaction.response.send_message(
            f"No promotions found for **{roblox_username}**.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"Promotions for {roblox_username}",
        color=discord.Color.blue()
    )
    for item in user_list:
        t = datetime.datetime.fromisoformat(item["time"])
        embed.add_field(
            name=f"Promotion {item['promotion_number']}",
            value=f"{item['old_rank']} ➔ {item['new_rank']} at <t:{int(t.timestamp())}:f>",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# ——— /demote ———
@bot.tree.command(name="demote", description="Demote a user by deleting one of their promotions.")
@app_commands.describe(
    roblox_username="Roblox username",
    promotion_number="The promotion number to delete",
    current_rank="Their current rank",
    demoted_rank="Rank to demote to",
    reason="Reason for demotion"
)
@app_commands.autocomplete(current_rank=rank_autocomplete, demoted_rank=rank_autocomplete)
async def demote(
    interaction: discord.Interaction,
    roblox_username: str,
    promotion_number: int,
    current_rank: str,
    demoted_rank: str,
    reason: str
):
    now = datetime.datetime.utcnow()

    user_list = promotions_db.get(roblox_username, [])
    if not user_list:
        await interaction.response.send_message(
            f"No promotions found for **{roblox_username}**.",
            ephemeral=True
        )
        return

    # Find and remove
    found = next((p for p in user_list if p["promotion_number"] == promotion_number), None)
    if not found:
        await interaction.response.send_message(
            f"❌ Promotion {promotion_number} not found for **{roblox_username}**.",
            ephemeral=True
        )
        return

    user_list.remove(found)
    save_json(PROMOTION_FILE, promotions_db)

    # Record demotion
    demo_list = demotions_db.setdefault(roblox_username, [])
    demo_list.append({
        "promotion_number": promotion_number,
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "time": now.isoformat()
    })
    save_json(DEMOTION_FILE, demotions_db)

    # Respond
    embed = discord.Embed(
        title="⚠️ Demotion Executed",
        color=discord.Color.red(),
        timestamp=now
    )
    embed.add_field(name="User",         value=roblox_username,       inline=True)
    embed.add_field(name="From Rank",    value=current_rank,          inline=True)
    embed.add_field(name="To Rank",      value=demoted_rank,          inline=True)
    embed.add_field(name="Reason",       value=reason,                inline=False)
    embed.add_field(name="Deleted Promo",value=str(promotion_number), inline=False)
    await interaction.response.send_message(embed=embed)

# ——— /demotions ———
@bot.tree.command(name="demotions", description="Show demotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(
    interaction: discord.Interaction,
    roblox_username: str
):
    user_list = demotions_db.get(roblox_username, [])
    if not user_list:
        await interaction.response.send_message(
            f"No demotions found for **{roblox_username}**.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"Demotions for {roblox_username}",
        color=discord.Color.dark_red()
    )
    for item in user_list:
        t = datetime.datetime.fromisoformat(item["time"])
        embed.add_field(
            name=f"Demotion of Promo #{item['promotion_number']}",
            value=(
                f"{item['current_rank']} ➔ {item['demoted_rank']}\n"
                f"Reason: {item['reason']}\n"
                f"At <t:{int(t.timestamp())}:f>"
            ),
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# ——— /help ———
@bot.tree.command(name="help", description="List all commands.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Command List",
        color=discord.Color.teal()
    )
    embed.add_field(name="/promote",   value="Promote a user with ranks & cooldown.", inline=False)
    embed.add_field(name="/promotions",value="View a user's promotion history.",       inline=False)
    embed.add_field(name="/demote",    value="Remove one promotion and record demotion.",inline=False)
    embed.add_field(name="/demotions", value="View a user's demotion history.",       inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ——— Run the bot ———
bot.run(os.getenv("DISCORD_TOKEN"))
