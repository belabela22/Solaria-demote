import discord
from discord import app_commands
from discord.ext import commands
import os
import threading
import datetime
import json
from flask import Flask

# --- Flask Keep-Alive for Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

# --- File paths ---
PROMOTION_FILE = "promotions.json"
DEMOTION_FILE  = "demotions.json"
COOLDOWN_FILE  = "cooldowns.json"

# --- JSON helpers ---
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# --- Load databases ---
promotions_db = load_json(PROMOTION_FILE, {})
demotions_db = load_json(DEMOTION_FILE, {})
cooldowns_db = load_json(COOLDOWN_FILE, {})

def save_all():
    save_json(PROMOTION_FILE, promotions_db)
    save_json(DEMOTION_FILE, demotions_db)
    save_json(COOLDOWN_FILE, cooldowns_db)

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Rank and Department Choices ---
RANK_OPTIONS = [app_commands.Choice(name=f"EL{i}", value=f"EL{i}") for i in range(1, 10)]
DEPARTMENT_OPTIONS = [
    app_commands.Choice(name="PR", value="PR"),
    app_commands.Choice(name="Medical", value="Medical"),
    app_commands.Choice(name="Surgical", value="Surgical"),
    app_commands.Choice(name="Nursing", value="Nursing"),
    app_commands.Choice(name="Paramedic", value="Paramedic")
]

# --- on_ready ---
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

# --- /promote Command ---
@bot.tree.command(name="promote", description="Promote a Roblox user (separate rank & department).")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Select the old rank",
    old_department="Select the old department",
    new_rank="Select the new rank",
    new_department="Select the new department",
    cooldown="Cooldown in hours (0 for none)"
)
@app_commands.choices(old_rank=RANK_OPTIONS, new_rank=RANK_OPTIONS, old_department=DEPARTMENT_OPTIONS, new_department=DEPARTMENT_OPTIONS)
async def promote(interaction: discord.Interaction, roblox_username: str, 
                  old_rank: app_commands.Choice[str], old_department: app_commands.Choice[str],
                  new_rank: app_commands.Choice[str], new_department: app_commands.Choice[str],
                  cooldown: float):
    now = datetime.datetime.utcnow()
    now_ts = int(now.timestamp())
    user = roblox_username.lower()

    # Check cooldown
    if user in cooldowns_db and now_ts < cooldowns_db[user]:
        await interaction.response.send_message(
            f"❌ {roblox_username} is on cooldown until <t:{cooldowns_db[user]}:R>.",
            ephemeral=True
        )
        return

    # Set cooldown
    if cooldown > 0:
        cooldowns_db[user] = now_ts + int(cooldown * 3600)
    else:
        cooldowns_db.pop(user, None)
    save_json(COOLDOWN_FILE, cooldowns_db)

    old_full = f"{old_rank.value} {old_department.value}"
    new_full = f"{new_rank.value} {new_department.value}"
    approver = interaction.user.name

    # Record promotion
    user_promos = promotions_db.setdefault(user, [])
    promo_number = len(user_promos) + 1
    user_promos.append({
        "promotion_number": promo_number,
        "old_rank": old_full,
        "new_rank": new_full,
        "approved_by": approver,
        "time": now.isoformat()
    })
    save_json(PROMOTION_FILE, promotions_db)

    embed = discord.Embed(
        title=f"✅ Promotion #{promo_number} Recorded!",
        color=discord.Color.green(),
        timestamp=now
    )
    embed.add_field(name="Username", value=roblox_username, inline=True)
    embed.add_field(name="Old Rank", value=old_full, inline=True)
    embed.add_field(name="New Rank", value=new_full, inline=True)
    embed.add_field(name="Approved By", value=approver, inline=True)
    await interaction.response.send_message(embed=embed)

# --- /promotions Command ---
@bot.tree.command(name="promotions", description="View promotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    user = roblox_username.lower()
    promos = promotions_db.get(user, [])
    if not promos:
        return await interaction.response.send_message(f"❌ No promotions found for {roblox_username}.", ephemeral=True)

    embed = discord.Embed(
        title=f"Promotions for {roblox_username}",
        color=discord.Color.blue()
    )
    for promo in promos:
        t = datetime.datetime.fromisoformat(promo["time"])
        embed.add_field(
            name=f"Promotion #{promo['promotion_number']}",
            value=(f"{promo['old_rank']} ➔ {promo['new_rank']}\n"
                   f"Approved by: {promo['approved_by']}\n"
                   f"At <t:{int(t.timestamp())}:f>"),
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# --- /demote Command ---
@bot.tree.command(name="demote", description="Demote a user by deleting one of their promotions and record the demotion.")
@app_commands.describe(
    roblox_username="Roblox username",
    promotion_number="Promotion number to delete (per user)",
    current_rank="Select current rank",
    current_department="Select current department",
    demoted_rank="Select demoted rank",
    demoted_department="Select demoted department",
    reason="Reason for demotion"
)
@app_commands.choices(current_rank=RANK_OPTIONS, current_department=DEPARTMENT_OPTIONS,
                      demoted_rank=RANK_OPTIONS, demoted_department=DEPARTMENT_OPTIONS)
async def demote(interaction: discord.Interaction, roblox_username: str, promotion_number: int,
                 current_rank: app_commands.Choice[str], current_department: app_commands.Choice[str],
                 demoted_rank: app_commands.Choice[str], demoted_department: app_commands.Choice[str],
                 reason: str):
    now = datetime.datetime.utcnow()
    user = roblox_username.lower()

    user_promos = promotions_db.get(user, [])
    if not user_promos:
        return await interaction.response.send_message(f"❌ No promotions found for {roblox_username}.", ephemeral=True)

    target = next((p for p in user_promos if p["promotion_number"] == promotion_number), None)
    if not target:
        return await interaction.response.send_message(f"❌ Promotion #{promotion_number} not found for {roblox_username}.", ephemeral=True)

    user_promos.remove(target)
    save_json(PROMOTION_FILE, promotions_db)

    demotions_db.setdefault(user, [])
    demo_number = len(demotions_db[user]) + 1
    current_full = f"{current_rank.value} {current_department.value}"
    demoted_full = f"{demoted_rank.value} {demoted_department.value}"
    demotions_db[user].append({
        "promotion_number": promotion_number,
        "current_rank": current_full,
        "demoted_rank": demoted_full,
        "reason": reason,
        "time": now.isoformat()
    })
    save_json(DEMOTION_FILE, demotions_db)

    embed = discord.Embed(
        title=f"⚠️ Demotion Recorded (Promo #{promotion_number} deleted)",
        color=discord.Color.red(),
        timestamp=now
    )
    embed.add_field(name="Username", value=roblox_username, inline=True)
    embed.add_field(name="To Rank", value=current_full, inline=True)
    embed.add_field(name="From Rank", value=demoted_full, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.response.send_message(embed=embed)

# --- /demotions Command ---
@bot.tree.command(name="demotions", description="View demotion history for a Roblox user.")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    user = roblox_username.lower()
    demos = demotions_db.get(user, [])
    if not demos:
        return await interaction.response.send_message(f"❌ No demotions found for {roblox_username}.", ephemeral=True)
    
    embed = discord.Embed(
        title=f"Demotions for {roblox_username}",
        color=discord.Color.dark_red()
    )
    for demo in demos:
        t = datetime.datetime.fromisoformat(demo["time"])
        embed.add_field(
            name=f"Demotion (from Promo #{demo['promotion_number']})",
            value=(f"{demo['demoted_rank']} ➔ {demo['current_rank']}\n"
                   f"Reason: {demo['reason']}\n"
                   f"At <t:{int(t.timestamp())}:f>"),
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# --- /help Command ---
@bot.tree.command(name="help", description="List all commands.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Bot Command List", color=discord.Color.teal())
    embed.add_field(name="/promote", value="Promote a user with rank & department.", inline=False)
    embed.add_field(name="/promotions", value="View user's promotions.", inline=False)
    embed.add_field(name="/demote", value="Demote user and record it.", inline=False)
    embed.add_field(name="/demotions", value="View user's demotions.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Run the Bot ---
bot.run(os.getenv("DISCORD_TOKEN"))
