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
cooldowns = {}

cooldown_timers = {
    "EL3->EL4": 2 * 60 * 60,
    "EL4->EL5": 12 * 60 * 60,
    "EL6->EL7": 48 * 60 * 60,
    "EL7->EL8": 72 * 60 * 60,
    "EL8->EL9": 120 * 60 * 60
}

def get_cooldown_seconds(old_rank, new_rank):
    key = f"{old_rank.upper()}->{new_rank.upper()}"
    return cooldown_timers.get(key)

async def get_roblox_avatar(username):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.roblox.com/users/get-by-username?username={username}") as resp:
                data = await resp.json()
                user_id = data.get("Id")
                if user_id:
                    async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png&isCircular=false") as t:
                        data = await t.json()
                        return data["data"][0]["imageUrl"]
    except:
        return None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(roblox_username="Roblox username", old_rank="Current rank", new_rank="Promoted rank")
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str):
    await interaction.response.defer()

    key = f"{roblox_username}_{old_rank}->{new_rank}"
    cooldown_seconds = get_cooldown_seconds(old_rank, new_rank)
    now = datetime.datetime.now().timestamp()

    if cooldown_seconds:
        last_time = cooldowns.get(key)
        if last_time and now - last_time < cooldown_seconds:
            wait = int((cooldown_seconds - (now - last_time)) // 60)
            await interaction.followup.send(f"Cooldown active. Try again in {wait} minutes.")
            return
        cooldowns[key] = now

    entry = {
        "old_rank": old_rank,
        "new_rank": new_rank,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "promoter": interaction.user.name
    }

    if roblox_username not in promotion_db:
        promotion_db[roblox_username] = []
    promotion_db[roblox_username].append(entry)

    avatar = await get_roblox_avatar(roblox_username)
    embed = discord.Embed(title=f"Promotion for {roblox_username}", color=discord.Color.green())
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.add_field(name="From", value=old_rank, inline=True)
    embed.add_field(name="To", value=new_rank, inline=True)
    embed.add_field(name="Promoted By", value=interaction.user.name)
    embed.add_field(name="Date", value=entry["date"])
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="promotions", description="Check promotion history")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    data = promotion_db.get(roblox_username)
    avatar = await get_roblox_avatar(roblox_username)
    if not data:
        embed = discord.Embed(title=f"No promotions for {roblox_username}", color=discord.Color.red())
        if avatar:
            embed.set_thumbnail(url=avatar)
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(title=f"Promotion History - {roblox_username}", color=discord.Color.blue())
    if avatar:
        embed.set_thumbnail(url=avatar)
    for i, promo in enumerate(data[-5:], 1):
        embed.add_field(name=f"Promotion {len(data) - 5 + i}", value=f"From {promo['old_rank']} to {promo['new_rank']} by {promo['promoter']} on {promo['date']}", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="demote", description="Demote a Roblox user")
@app_commands.describe(roblox_username="Roblox username", current_rank="Current rank", demoted_rank="Demoted rank", reason="Reason for demotion")
async def demote(interaction: discord.Interaction, roblox_username: str, current_rank: str, demoted_rank: str, reason: str):
    await interaction.response.defer()

    demotion = {
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "demoter": interaction.user.name
    }

    if roblox_username not in demotion_db:
        demotion_db[roblox_username] = []
    demotion_db[roblox_username].append(demotion)

    if roblox_username in promotion_db and promotion_db[roblox_username]:
        promotion_db[roblox_username].pop()

    avatar = await get_roblox_avatar(roblox_username)
    embed = discord.Embed(title=f"Demotion for {roblox_username}", color=discord.Color.red())
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.add_field(name="From", value=current_rank, inline=True)
    embed.add_field(name="To", value=demoted_rank, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Demoted By", value=interaction.user.name)
    embed.add_field(name="Date", value=demotion["date"])
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="demotions", description="Check demotion history")
@app_commands.describe(roblox_username="Roblox username")
async def demotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    data = demotion_db.get(roblox_username)
    avatar = await get_roblox_avatar(roblox_username)
    if not data:
        embed = discord.Embed(title=f"No demotions for {roblox_username}", color=discord.Color.red())
        if avatar:
            embed.set_thumbnail(url=avatar)
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(title=f"Demotion History - {roblox_username}", color=discord.Color.dark_red())
    if avatar:
        embed.set_thumbnail(url=avatar)
    for i, demotion in enumerate(data[-5:], 1):
        embed.add_field(
            name=f"Demotion {len(data) - 5 + i}",
            value=f"From {demotion['current_rank']} to {demotion['demoted_rank']} by {demotion['demoter']} on {demotion['date']}\nReason: {demotion['reason']}",
            inline=False
        )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="delete_promo", description="Delete specific promotion entries")
@app_commands.describe(roblox_username="Roblox username", from_num="From number", to_num="To number (optional)")
async def delete_promo(interaction: discord.Interaction, roblox_username: str, from_num: int, to_num: int = None):
    await interaction.response.defer()

    if roblox_username not in promotion_db or not promotion_db[roblox_username]:
        await interaction.followup.send(f"No promotions found for {roblox_username}.")
        return

    promos = promotion_db[roblox_username]
    to_num = to_num or from_num
    if from_num < 1 or to_num > len(promos) or from_num > to_num:
        await interaction.followup.send("Invalid range.")
        return

    del promos[from_num - 1:to_num]
    await interaction.followup.send(f"Deleted promotions {from_num} to {to_num} for {roblox_username}.")

bot.run(os.getenv("DISCORD_TOKEN"))
