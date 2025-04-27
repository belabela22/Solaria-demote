import discord
from discord import app_commands
from discord.ext import commands
import os
import datetime
import json
from flask import Flask
import threading

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

# Rank choices (grouped by categories)
rank_choices = [
    # Public Relations
    discord.app_commands.Choice(name="EL1 PR", value="EL1 PR"),
    discord.app_commands.Choice(name="EL2 PR", value="EL2 PR"),
    discord.app_commands.Choice(name="EL3 PR", value="EL3 PR"),
    discord.app_commands.Choice(name="EL4 PR", value="EL4 PR"),
    discord.app_commands.Choice(name="EL5 PR", value="EL5 PR"),
    discord.app_commands.Choice(name="EL6 PR", value="EL6 PR"),
    discord.app_commands.Choice(name="EL7 PR", value="EL7 PR"),
    discord.app_commands.Choice(name="EL8 PR", value="EL8 PR"),
    discord.app_commands.Choice(name="EL9 PR", value="EL9 PR"),

    # Medical
    discord.app_commands.Choice(name="EL1 Medical", value="EL1 Medical"),
    discord.app_commands.Choice(name="EL2 Medical", value="EL2 Medical"),
    discord.app_commands.Choice(name="EL3 Medical", value="EL3 Medical"),
    discord.app_commands.Choice(name="EL4 Medical", value="EL4 Medical"),
    discord.app_commands.Choice(name="EL5 Medical", value="EL5 Medical"),
    discord.app_commands.Choice(name="EL6 Medical", value="EL6 Medical"),
    discord.app_commands.Choice(name="EL7 Medical", value="EL7 Medical"),
    discord.app_commands.Choice(name="EL8 Medical", value="EL8 Medical"),
    discord.app_commands.Choice(name="EL9 Medical", value="EL9 Medical"),

    # Surgical
    discord.app_commands.Choice(name="EL1 Surgical", value="EL1 Surgical"),
    discord.app_commands.Choice(name="EL2 Surgical", value="EL2 Surgical"),
    discord.app_commands.Choice(name="EL3 Surgical", value="EL3 Surgical"),
    discord.app_commands.Choice(name="EL4 Surgical", value="EL4 Surgical"),
    discord.app_commands.Choice(name="EL5 Surgical", value="EL5 Surgical"),
    discord.app_commands.Choice(name="EL6 Surgical", value="EL6 Surgical"),
    discord.app_commands.Choice(name="EL7 Surgical", value="EL7 Surgical"),
    discord.app_commands.Choice(name="EL8 Surgical", value="EL8 Surgical"),
    discord.app_commands.Choice(name="EL9 Surgical", value="EL9 Surgical"),

    # Nursing
    discord.app_commands.Choice(name="EL1 Nursing", value="EL1 Nursing"),
    discord.app_commands.Choice(name="EL2 Nursing", value="EL2 Nursing"),
    discord.app_commands.Choice(name="EL3 Nursing", value="EL3 Nursing"),
    discord.app_commands.Choice(name="EL4 Nursing", value="EL4 Nursing"),
    discord.app_commands.Choice(name="EL5 Nursing", value="EL5 Nursing"),
    discord.app_commands.Choice(name="EL6 Nursing", value="EL6 Nursing"),
    discord.app_commands.Choice(name="EL7 Nursing", value="EL7 Nursing"),
    discord.app_commands.Choice(name="EL8 Nursing", value="EL8 Nursing"),
    discord.app_commands.Choice(name="EL9 Nursing", value="EL9 Nursing"),

    # Paramedic
    discord.app_commands.Choice(name="EL1 Paramedic", value="EL1 Paramedic"),
    discord.app_commands.Choice(name="EL2 Paramedic", value="EL2 Paramedic"),
    discord.app_commands.Choice(name="EL3 Paramedic", value="EL3 Paramedic"),
    discord.app_commands.Choice(name="EL4 Paramedic", value="EL4 Paramedic"),
    discord.app_commands.Choice(name="EL5 Paramedic", value="EL5 Paramedic"),
    discord.app_commands.Choice(name="EL6 Paramedic", value="EL6 Paramedic"),
    discord.app_commands.Choice(name="EL7 Paramedic", value="EL7 Paramedic"),
    discord.app_commands.Choice(name="EL8 Paramedic", value="EL8 Paramedic"),
    discord.app_commands.Choice(name="EL9 Paramedic", value="EL9 Paramedic"),
]

# Slash command to promote
@bot.tree.command(name="promote", description="Promote a Roblox user with a cooldown.")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank of the user",
    new_rank="New rank of the user",
    cooldown="Cooldown in hours (example: 2 for 2 hours)"
)
@app_commands.choices(
    old_rank=rank_choices,
    new_rank=rank_choices
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
