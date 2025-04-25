import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
from flask import Flask
import threading
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Start the web server in a new thread
threading.Thread(target=run_web).start()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)
cooldowns_file = "cooldowns.json"

# Cooldown durations in seconds
cooldown_mapping = {
    "El3": {"El4": 2 * 3600},      # 2 hours
    "El4": {"El5": 12 * 3600},     # 12 hours
    "El5": {"El6": 0},
    "El6": {"El7": 48 * 3600},     # 2 days
    "El7": {"El8": 72 * 3600},     # 3 days
    "El8": {"El9": 120 * 3600}     # 5 days
}

# Load cooldown data
if os.path.exists(cooldowns_file):
    with open(cooldowns_file, "r") as f:
        cooldowns = json.load(f)
else:
    cooldowns = {}

def save_cooldowns():
    with open(cooldowns_file, "w") as f:
        json.dump(cooldowns, f, indent=4)

def get_seconds_remaining(last_time, cooldown_duration):
    remaining = last_time + cooldown_duration - int(time.time())
    return remaining if remaining > 0 else 0

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} is online!")

@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(
    roblox_username="Username to promote",
    old_rank="Current rank (e.g. El3 medical)",
    new_rank="New rank (e.g. El4 medical)"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str):
    user_key = roblox_username.lower()
    rank_from = old_rank.split()[0]
    rank_to = new_rank.split()[0]

    # Determine cooldown (if any)
    cooldown_time = cooldown_mapping.get(rank_from, {}).get(rank_to)

    if cooldown_time is not None:
        user_cooldown = cooldowns.get(user_key, {})
        key = f"{rank_from}_{rank_to}"
        last_time = user_cooldown.get(key, 0)

        seconds_remaining = get_seconds_remaining(last_time, cooldown_time)

        if seconds_remaining > 0:
            hours = seconds_remaining // 3600
            minutes = (seconds_remaining % 3600) // 60
            embed = discord.Embed(
                title="Cooldown Active",
                description=f"**{roblox_username}** can't be promoted from **{old_rank}** to **{new_rank}** yet.",
                color=discord.Color.red()
            )
            embed.add_field(name="Time Left", value=f"{hours}h {minutes}m", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        else:
            # Update cooldown
            user_cooldown[key] = int(time.time())
            cooldowns[user_key] = user_cooldown
            save_cooldowns()

    # Proceed with promotion (log it or show embed)
    embed = discord.Embed(
        title="Promotion Successful",
        description=f"**{roblox_username}** has been promoted from **{old_rank}** to **{new_rank}**.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)
# Run the bot
bot.run('YOUR_BOT_TOKEN')
