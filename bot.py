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
STAFF_FILE = "staff.json"  # New staff file

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
staff_db = load_json(STAFF_FILE, {})  # Load staff database

def save_all():
    save_json(PROMOTION_FILE, promotions_db)
    save_json(DEMOTION_FILE, demotions_db)
    save_json(COOLDOWN_FILE, cooldowns_db)
    save_json(STAFF_FILE, staff_db)  # Save staff database

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

# --- /createfile Command ---
@bot.tree.command(name="createfile", description="Create a staff record with their information.")
@app_commands.describe(
    real_name="Real name of the staff member",
    roblox_username="Roblox username of the staff member",
    current_rank="Current rank of the staff member",
    current_department="Current department of the staff member"
)
@app_commands.choices(current_rank=RANK_OPTIONS, current_department=DEPARTMENT_OPTIONS)
async def createfile(interaction: discord.Interaction, real_name: str, roblox_username: str,
                     current_rank: app_commands.Choice[str], current_department: app_commands.Choice[str]):
    user = roblox_username.lower()

    if user in staff_db:
        await interaction.response.send_message(f"❌ Staff record already exists for {roblox_username}.", ephemeral=True)
        return

    staff_db[user] = {
        "real_name": real_name,
        "roblox_username": roblox_username,
        "current_rank": current_rank.value,
        "current_department": current_department.value
    }
    save_json(STAFF_FILE, staff_db)

    await interaction.response.send_message(f"✅ Staff record created for {roblox_username}.", ephemeral=True)

# --- /promote Command ---
@bot.tree.command(name="promote", description="Promote a Roblox user (separate rank & department).")
@app_commands.describe(
    roblox_username="Roblox username",
    new_rank="Select the new rank",
    new_department="Select the new department (optional)"
)
@app_commands.choices(new_rank=RANK_OPTIONS, new_department=DEPARTMENT_OPTIONS)
async def promote(interaction: discord.Interaction, roblox_username: str,
                  new_rank: app_commands.Choice[str], new_department: app_commands.Choice[str] = None):
    user = roblox_username.lower()

    if user not in staff_db:
        await interaction.response.send_message(f"❌ No staff record found for {roblox_username}.", ephemeral=True)
        return

    # Load old rank and department
    old_rank = staff_db[user]["current_rank"]
    old_department = staff_db[user]["current_department"]

    # Set new rank and department
    if new_department:
        staff_db[user]["current_rank"] = new_rank.value
        staff_db[user]["current_department"] = new_department.value
    else:
        staff_db[user]["current_rank"] = new_rank.value
        staff_db[user]["current_department"] = old_department  # Keep old department if not updated

    save_json(STAFF_FILE, staff_db)

    # Record promotion in promotions DB
    now = datetime.datetime.utcnow()
    now_ts = int(now.timestamp())
    approver = interaction.user.name
    user_promos = promotions_db.setdefault(user, [])
    promo_number = len(user_promos) + 1
    user_promos.append({
        "promotion_number": promo_number,
        "old_rank": f"{old_rank} {old_department}",
        "new_rank": f"{new_rank.value} {staff_db[user]['current_department']}",
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
    embed.add_field(name="Old Rank", value=f"{old_rank} {old_department}", inline=True)
    embed.add_field(name="New Rank", value=f"{new_rank.value} {staff_db[user]['current_department']}", inline=True)
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
    embed.add_field(name="From Rank", value=current_full, inline=True)
    embed.add_field(name="To Rank", value=demoted_full, inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)
    embed.add_field(name="Time", value=f"<t:{int(now.timestamp())}:f>", inline=True)

    await interaction.response.send_message(embed=embed)

# --- Run the bot ---
bot.run("YOUR_DISCORD_BOT_TOKEN")
