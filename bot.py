import discord
from discord.ext import commands, tasks
import json
import os
from flask import Flask
import threading
import time

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot with the required intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)

# Port from the environment variable (Render will automatically set it)
PORT = os.environ.get("PORT", 5000)

# Cooldown data (stored in a JSON file)
cooldown_file = "cooldown.json"

# Load the cooldown data from the file (if exists)
def load_cooldowns():
    if os.path.exists(cooldown_file):
        with open(cooldown_file, 'r') as f:
            return json.load(f)
    return {}

# Save the cooldown data to the file
def save_cooldowns(cooldowns):
    with open(cooldown_file, 'w') as f:
        json.dump(cooldowns, f, indent=4)

# Cooldown check based on ranks
cooldown_data = {
    "El1": {"El2": 0},
    "El2": {"El3": 2 * 3600},  # 2 hours
    "El3": {"El4": 12 * 3600},  # 12 hours
    "El4": {"El5": 0},
    "El5": {"El6": 48 * 3600},  # 48 hours
    "El6": {"El7": 72 * 3600},  # 72 hours
    "El7": {"El8": 120 * 3600},  # 120 hours
    "El8": {"El9": 0},
}

@app.route('/')
def index():
    return 'Bot is running!'

# Function to run the Flask app in a separate thread
def run():
    app.run(host="0.0.0.0", port=PORT)

# Start Flask server in a separate thread
thread = threading.Thread(target=run)
thread.start()

# Check if the promotion is in cooldown
def is_in_cooldown(user_id, old_rank, new_rank):
    cooldowns = load_cooldowns()
    if user_id not in cooldowns:
        return False, 0  # No cooldown found
    user_data = cooldowns[user_id]
    if old_rank not in user_data or new_rank not in cooldown_data[old_rank]:
        return False, 0
    last_promotion_time = user_data.get(new_rank)
    if last_promotion_time:
        time_left = last_promotion_time + cooldown_data[old_rank][new_rank] - time.time()
        return time_left > 0, time_left
    return False, 0

# Command to promote users
@bot.command()
async def promote(ctx, roblox_user: str, old_rank: str, new_rank: str):
    user_id = str(ctx.author.id)  # Using author ID to track the cooldowns
    in_cooldown, time_left = is_in_cooldown(user_id, old_rank, new_rank)
    
    if in_cooldown:
        # Send a message saying the promotion is in cooldown
        await ctx.send(f"Promotion from {old_rank} to {new_rank} is in cooldown. Time left: {time_left:.2f} seconds.")
        return

    # Register the promotion time
    cooldowns = load_cooldowns()
    if user_id not in cooldowns:
        cooldowns[user_id] = {}
    cooldowns[user_id][new_rank] = time.time()
    save_cooldowns(cooldowns)

    # Send a success message
    await ctx.send(f"{roblox_user} has been promoted from {old_rank} to {new_rank}!")

# Command to show all promotions
@bot.command()
async def promotions(ctx):
    cooldowns = load_cooldowns()
    embed = discord.Embed(title="Promotion History", color=discord.Color.blue())
    for user_id, user_data in cooldowns.items():
        for rank, time_promotion in user_data.items():
            embed.add_field(name=f"User {user_id}", value=f"Rank: {rank}, Promoted At: {time_promotion}", inline=False)
    await ctx.send(embed=embed)

# Command to demote users
@bot.command()
async def demote(ctx, roblox_user: str, old_rank: str, new_rank: str, reason: str):
    user_id = str(ctx.author.id)
    cooldowns = load_cooldowns()
    
    if user_id in cooldowns:
        user_data = cooldowns[user_id]
        if new_rank in user_data:
            del user_data[new_rank]  # Delete the demoted rank
            save_cooldowns(cooldowns)
            await ctx.send(f"{roblox_user} has been demoted from {old_rank} to {new_rank}. Reason: {reason}")
        else:
            await ctx.send(f"No promotion record found for {roblox_user} in the rank {new_rank}.")
    else:
        await ctx.send(f"No promotion record found for {roblox_user}.")

# Run the bot
bot.run('YOUR_BOT_TOKEN')
