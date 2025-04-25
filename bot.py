import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

promotion_db = {}
demotion_db = {}
promotion_timestamps = {}

cooldown_hours = {
    ("El3", "El4"): 2,
    ("El4", "El5"): 12,
    ("El5", "El6"): 0,
    ("El6", "El7"): 48,
    ("El7", "El8"): 72,
    ("El8", "El9"): 120,
}

async def get_roblox_avatar(roblox_username: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.roblox.com/users/get-by-username?username={roblox_username}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    user_id = data.get("Id")
                    if user_id:
                        async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png&isCircular=false") as thumb_resp:
                            if thumb_resp.status == 200:
                                thumb_data = await thumb_resp.json()
                                return thumb_data["data"][0]["imageUrl"]
    except Exception as e:
        print(f"Error fetching Roblox avatar: {e}")
    return None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Current rank",
    new_rank="New rank"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str):
    await interaction.response.defer()
    key = roblox_username.lower()
    cooldown_key = (old_rank, new_rank)

    now = datetime.datetime.now()
    last_time = promotion_timestamps.get(key, {}).get(cooldown_key)

    if cooldown_key in cooldown_hours:
        cooldown = cooldown_hours[cooldown_key]
        if last_time and (now - last_time).total_seconds() < cooldown * 3600:
            remaining = timedelta(hours=cooldown) - (now - last_time)
            embed = discord.Embed(
                title="Promotion Cooldown",
                description=f"Promotion is in cooldown.\nTime left: {remaining}",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            return

    if key not in promotion_timestamps:
        promotion_timestamps[key] = {}
    promotion_timestamps[key][cooldown_key] = now

    current_date = now.strftime("%Y-%m-%d %H:%M:%S")
    promoter = interaction.user.name
    promotion_entry = {
        "old_rank": old_rank,
        "new_rank": new_rank,
        "date": current_date,
        "promoter": promoter
    }
    if key not in promotion_db:
        promotion_db[key] = []
    promotion_db[key].append(promotion_entry)
    avatar_url = await get_roblox_avatar(roblox_username)
    embed = discord.Embed(title=f"Promotion for {roblox_username}", color=discord.Color.green())
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    embed.add_field(name="From", value=old_rank, inline=True)
    embed.add_field(name="To", value=new_rank, inline=True)
    embed.add_field(name="By", value=promoter, inline=False)
    embed.add_field(name="Date", value=current_date, inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="promotions", description="View promotion history")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    key = roblox_username.lower()
    avatar_url = await get_roblox_avatar(roblox_username)
    history = promotion_db.get(key, [])
    if not history:
        embed = discord.Embed(title=f"No promotions found for {roblox_username}", color=discord.Color.red())
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        await interaction.followup.send(embed=embed)
        return
    embed = discord.Embed(title=f"Promotion History: {roblox_username}", color=discord.Color.blue())
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    for i, p in enumerate(history[-5:], 1):
        embed.add_field(name=f"Promotion {i}", value=f"From: {p['old_rank']} → To: {p['new_rank']}\nBy: {p['promoter']}\nOn: {p['date']}", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="demote", description="Demote a Roblox user")
@app_commands.describe(
    roblox_username="Roblox username",
    current_rank="Current rank before demotion",
    demoted_rank="New demoted rank",
    reason="Reason for demotion"
)
async def demote(interaction: discord.Interaction, roblox_username: str, current_rank: str, demoted_rank: str, reason: str):
    await interaction.response.defer()
    key = roblox_username.lower()
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    demoter = interaction.user.name
    demotion_entry = {
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "date": current_date,
        "demoter": demoter,
        "reason": reason
    }
    if key not in demotion_db:
        demotion_db[key] = []
    demotion_db[key].append(demotion_entry)

    if key in promotion_db and promotion_db[key]:
        promotion_db[key].pop()

    avatar_url = await get_roblox_avatar(roblox_username)
    embed = discord.Embed(title=f"Demotion for {roblox_username}", color=discord.Color.red())
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    embed.add_field(name="From", value=current_rank, inline=True)
    embed.add_field(name="To", value=demoted_rank, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="By", value=demoter, inline=False)
    embed.add_field(name="Date", value=current_date, inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="demotions", description="View demotion history")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    key = roblox_username.lower()
    avatar_url = await get_roblox_avatar(roblox_username)
    history = demotion_db.get(key, [])
    if not history:
        embed = discord.Embed(title=f"No demotions found for {roblox_username}", color=discord.Color.red())
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        await interaction.followup.send(embed=embed)
        return
    embed = discord.Embed(title=f"Demotion History: {roblox_username}", color=discord.Color.dark_red())
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    for i, d in enumerate(history[-5:], 1):
        embed.add_field(name=f"Demotion {i}", value=f"From: {d['current_rank']} → To: {d['demoted_rank']}\nReason: {d['reason']}\nBy: {d['demoter']}\nOn: {d['date']}", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="delete_promo", description="Delete promotion(s) by number")
@app_commands.describe(
    roblox_username="Roblox username",
    from_number="From number",
    to_number="To number (optional)"
)
async def delete_promo(interaction: discord.Interaction, roblox_username: str, from_number: int, to_number: int = None):
    await interaction.response.defer()
    key = roblox_username.lower()
    if key not in promotion_db:
        await interaction.followup.send(f"No promotions found for {roblox_username}.")
        return
    promotions = promotion_db[key]
    if to_number is None:
        if 0 < from_number <= len(promotions):
            removed = promotions.pop(from_number - 1)
            await interaction.followup.send(f"Deleted promotion {from_number}: {removed['old_rank']} → {removed['new_rank']}")
        else:
            await interaction.followup.send("Invalid number.")
    else:
        to_number = min(to_number, len(promotions))
        if 0 < from_number <= to_number:
            del promotions[from_number - 1:to_number]
            await interaction.followup.send(f"Deleted promotions from {from_number} to {to_number}.")
        else:
            await interaction.followup.send("Invalid range.")

bot.run(os.getenv("DISCORD_TOKEN"))
