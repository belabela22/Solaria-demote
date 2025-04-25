import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask

# Web server to keep bot alive on Render
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"
def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_web).start()

# Set up bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Databases
promotion_db = {}
demotion_db = {}
cooldown_tracker = {}

cooldowns = {
    ("EL3", "EL4"): 2,
    ("EL4", "EL5"): 12,
    ("EL6", "EL7"): 48,
    ("EL7", "EL8"): 72,
    ("EL8", "EL9"): 120
}

async def get_roblox_avatar(username: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.roblox.com/users/get-by-username?username={username}") as resp:
                data = await resp.json()
                user_id = data.get("Id")
                if user_id:
                    async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png") as thumb:
                        thumb_data = await thumb.json()
                        return thumb_data["data"][0]["imageUrl"]
    except Exception as e:
        print(f"Avatar fetch error: {e}")
    return None

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user.name}")

@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(roblox_username="Roblox username", old_rank="Old rank", new_rank="New rank")
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str):
    await interaction.response.defer()
    key = (old_rank.upper(), new_rank.upper())
    now = datetime.datetime.now()

    # Check cooldown tracker for this user and promotion
    if roblox_username not in cooldown_tracker:
        cooldown_tracker[roblox_username] = {}

    if key in cooldowns:
        last_promotion_time = cooldown_tracker[roblox_username].get(key)
        if last_promotion_time:
            time_diff = (now - last_promotion_time).total_seconds()
            if time_diff < cooldowns[key] * 3600:  # In cooldown
                remaining_time = cooldowns[key] * 3600 - time_diff
                remaining_minutes = int(remaining_time / 60)
                await interaction.followup.send(f"Promotion is in cooldown. Please wait {remaining_minutes} more minutes.")
                return

    # If no cooldown or cooldown is over, proceed with promotion
    cooldown_tracker[roblox_username][key] = now

    # Register promotion
    date = now.strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "old_rank": old_rank,
        "new_rank": new_rank,
        "date": date,
        "promoter": interaction.user.name
    }
    promotion_db.setdefault(roblox_username, []).append(entry)

    avatar = await get_roblox_avatar(roblox_username)
    embed = discord.Embed(title=f"Promotion for {roblox_username}", color=discord.Color.green())
    if avatar: embed.set_thumbnail(url=avatar)
    embed.add_field(name="Previous Rank", value=old_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)
    embed.add_field(name="Promoted By", value=interaction.user.name, inline=False)
    embed.add_field(name="Date", value=date, inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="promotions", description="See a user's promotion history")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    avatar = await get_roblox_avatar(roblox_username)
    history = promotion_db.get(roblox_username, [])
    if not history:
        embed = discord.Embed(title="No promotions found.", color=discord.Color.red())
        if avatar: embed.set_thumbnail(url=avatar)
        await interaction.followup.send(embed=embed)
        return
    embed = discord.Embed(title=f"Promotion History for {roblox_username}", color=discord.Color.blue())
    if avatar: embed.set_thumbnail(url=avatar)
    for i, promo in enumerate(history[-5:], 1):
        embed.add_field(
            name=f"Promotion {len(history) - 5 + i}",
            value=f"From {promo['old_rank']} to {promo['new_rank']}\nBy: {promo['promoter']}\nOn: {promo['date']}",
            inline=False
        )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="demote", description="Demote a user and log the reason")
@app_commands.describe(roblox_username="Roblox username", current_rank="Current rank", demoted_rank="Demoted to", reason="Reason for demotion")
async def demote(interaction: discord.Interaction, roblox_username: str, current_rank: str, demoted_rank: str, reason: str):
    await interaction.response.defer()
    if roblox_username in promotion_db and promotion_db[roblox_username]:
        promotion_db[roblox_username].pop()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "demoter": interaction.user.name,
        "date": now
    }
    demotion_db.setdefault(roblox_username, []).append(entry)
    avatar = await get_roblox_avatar(roblox_username)
    embed = discord.Embed(title=f"Demotion for {roblox_username}", color=discord.Color.red())
    if avatar: embed.set_thumbnail(url=avatar)
    embed.add_field(name="Previous Rank", value=current_rank, inline=True)
    embed.add_field(name="New Rank", value=demoted_rank, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Demoted By", value=interaction.user.name, inline=False)
    embed.add_field(name="Date", value=now, inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="demotions", description="See a user's demotion history")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    history = demotion_db.get(roblox_username, [])
    avatar = await get_roblox_avatar(roblox_username)
    if not history:
        embed = discord.Embed(title="No demotions found.", color=discord.Color.red())
        if avatar: embed.set_thumbnail(url=avatar)
        await interaction.followup.send(embed=embed)
        return
    embed = discord.Embed(title=f"Demotion History for {roblox_username}", color=discord.Color.dark_red())
    if avatar: embed.set_thumbnail(url=avatar)
    for i, demotion in enumerate(history[-5:], 1):
        embed.add_field(
            name=f"Demotion {len(history) - 5 + i}",
            value=f"From {demotion['current_rank']} to {demotion['demoted_rank']}\nReason: {demotion['reason']}\nBy: {demotion['demoter']}\nOn: {demotion['date']}",
            inline=False
        )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="delete_promo", description="Delete promotions by number or range")
@app_commands.describe(roblox_username="Roblox username", number="Number or range (e.g. 2 or 2-4)")
async def delete_promo(interaction: discord.Interaction, roblox_username: str, number: str):
    await interaction.response.defer()
    if roblox_username not in promotion_db or not promotion_db[roblox_username]:
        await interaction.followup.send("No promotions found.")
        return
    try:
        if '-' in number:
            start, end = map(int, number.split('-'))
            del promotion_db[roblox_username][start-1:end]
        else:
            del promotion_db[roblox_username][int(number)-1]
        await interaction.followup.send(f"Promotion(s) deleted successfully.")
    except:
        await interaction.followup.send("Invalid number or range provided.")

# Run bot
bot.run(os.getenv("DISCORD_TOKEN"))
