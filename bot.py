import discord
import os
import json
from discord.ext import commands
from datetime import datetime, timedelta

# Load or initialize promotion and demotion data
promo_file = "promotions.json"
demotion_file = "demotions.json"

if not os.path.exists(promo_file):
    with open(promo_file, "w") as f:
        json.dump({}, f)

if not os.path.exists(demotion_file):
    with open(demotion_file, "w") as f:
        json.dump({}, f)

intents = discord.Intents.default()
intents.message_content = True  # Enable the necessary intents

bot = commands.Bot(command_prefix="/", intents=intents)

# Global cooldowns for each promotion rank
cooldowns = {
    "El1 to El2": timedelta(hours=2),
    "El2 to El3": timedelta(hours=12),
    "El3 to El4": timedelta(hours=24),
    "El4 to El5": timedelta(hours=48),
    "El5 to El6": timedelta(days=1),
    "El6 to El7": timedelta(days=2),
    "El7 to El8": timedelta(days=3),
    "El8 to El9": timedelta(days=5),
}

# Helper function to load data from the file
def load_data(filename):
    with open(filename, "r") as f:
        return json.load(f)

# Helper function to save data to the file
def save_data(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# Promote Command
@bot.command()
async def promote(ctx, roblox_username: str, old_rank: str, new_rank: str):
    user_data = load_data(promo_file)

    # Create unique promotion identifier
    promotion_key = f"{roblox_username}-{old_rank}-{new_rank}"

    if promotion_key in user_data:
        last_promotion_time = datetime.strptime(user_data[promotion_key], "%Y-%m-%d %H:%M:%S")
        remaining_time = last_promotion_time + cooldowns.get(f"{old_rank} to {new_rank}", timedelta()) - datetime.now()
        
        if remaining_time > timedelta(0):
            await ctx.send(f"Promotion is in cooldown. Time remaining: {str(remaining_time)}")
            return

    # Update last promotion time and save data
    user_data[promotion_key] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(promo_file, user_data)

    await ctx.send(f"{roblox_username} has been promoted from {old_rank} to {new_rank}.")

# Demote Command
@bot.command()
async def demote(ctx, roblox_username: str, current_rank: str, demoted_rank: str, reason: str):
    demotion_data = load_data(demotion_file)

    demotion_key = f"{roblox_username}-{current_rank}-{demoted_rank}"

    # Log the demotion
    demotion_data[demotion_key] = {
        "roblox_username": roblox_username,
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_data(demotion_file, demotion_data)

    await ctx.send(f"{roblox_username} has been demoted from {current_rank} to {demoted_rank}. Reason: {reason}")

# View Promotions History Command
@bot.command()
async def promotions(ctx):
    user_data = load_data(promo_file)

    embed = discord.Embed(title="Promotion History", description="Listing all promotions.", color=discord.Color.green())
    for key, value in user_data.items():
        roblox_username, old_rank, new_rank = key.split('-')
        embed.add_field(name=f"{roblox_username}: {old_rank} -> {new_rank}", value=f"Last promoted: {value}", inline=False)

    await ctx.send(embed=embed)

# View Demotions History Command
@bot.command()
async def demotions(ctx):
    demotion_data = load_data(demotion_file)

    embed = discord.Embed(title="Demotion History", description="Listing all demotions.", color=discord.Color.red())
    for key, details in demotion_data.items():
        embed.add_field(
            name=f"{details['roblox_username']}: {details['current_rank']} -> {details['demoted_rank']}",
            value=f"Reason: {details['reason']} - Time: {details['timestamp']}",
            inline=False,
        )

    await ctx.send(embed=embed)

# Delete Promotion Command
@bot.command()
async def delete_promo(ctx, promo_number: int):
    user_data = load_data(promo_file)

    # Find promotion by number
    promotion_keys = list(user_data.keys())
    if 0 < promo_number <= len(promotion_keys):
        promotion_key = promotion_keys[promo_number - 1]
        del user_data[promotion_key]
        save_data(promo_file, user_data)
        await ctx.send(f"Promotion {promo_number} has been deleted.")
    else:
        await ctx.send("Invalid promotion number.")

# Delete Demotion Command
@bot.command()
async def delete_demotion(ctx, demotion_number: int):
    demotion_data = load_data(demotion_file)

    # Find demotion by number
    demotion_keys = list(demotion_data.keys())
    if 0 < demotion_number <= len(demotion_keys):
        demotion_key = demotion_keys[demotion_number - 1]
        del demotion_data[demotion_key]
        save_data(demotion_file, demotion_data)
        await ctx.send(f"Demotion {demotion_number} has been deleted.")
    else:
        await ctx.send("Invalid demotion number.")

# Start the bot with the token
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
