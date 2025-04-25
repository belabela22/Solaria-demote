import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os

# Set up bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

promotion_db = {}
cooldown_tracker = {}

cooldown_hours = {
    "El3": {"El4": 2},
    "El4": {"El5": 12},
    "El5": {"El6": 0},
    "El6": {"El7": 48},
    "El7": {"El8": 72},
    "El8": {"El9": 120},
}

async def get_avatar(username: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.roblox.com/users/get-by-username?username={username}") as resp:
            data = await resp.json()
            user_id = data.get("Id")
        async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png&isCircular=false") as thumb_resp:
            thumb_data = await thumb_resp.json()
            return thumb_data["data"][0]["imageUrl"]

def extract_el_and_category(rank: str):
    parts = rank.split()
    return parts[0], parts[1] if len(parts) > 1 else ""

@bot.tree.command(name="promote", description="Promote a Roblox user")
@app_commands.describe(
    roblox_username="Roblox username",
    old_rank="Old rank",
    new_rank="New rank"
)
async def promote(interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str):
    await interaction.response.defer()
    promoter = interaction.user.name
    now = datetime.datetime.now()

    old_el, old_cat = extract_el_and_category(old_rank)
    new_el, new_cat = extract_el_and_category(new_rank)

    if old_cat.lower() != new_cat.lower():
        await interaction.followup.send("Category mismatch between ranks.")
        return

    cooldown = cooldown_hours.get(old_el, {}).get(new_el)
    user_key = f"{roblox_username}_{old_cat.lower()}"
    last_promo_time = cooldown_tracker.get(user_key, {}).get(old_el)

    if cooldown and last_promo_time:
        delta = now - last_promo_time
        if delta.total_seconds() < cooldown * 3600:
            remaining = (cooldown * 3600 - delta.total_seconds()) / 3600
            await interaction.followup.send(
                f"**Promotion is on cooldown** for {roblox_username}.\nRemaining time: **{remaining:.1f} hours**"
            )
            return

    # Update cooldown tracker
    if user_key not in cooldown_tracker:
        cooldown_tracker[user_key] = {}
    cooldown_tracker[user_key][old_el] = now

    if roblox_username not in promotion_db:
        promotion_db[roblox_username] = []
    promotion_db[roblox_username].append({
        "old_rank": old_rank,
        "new_rank": new_rank,
        "date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "promoter": promoter
    })

    avatar = await get_avatar(roblox_username)
    embed = discord.Embed(title=f"🎉 Promotion for {roblox_username}", color=discord.Color.green())
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.add_field(name="From", value=old_rank, inline=True)
    embed.add_field(name="To", value=new_rank, inline=True)
    embed.add_field(name="By", value=promoter, inline=False)
    embed.add_field(name="Date", value=now.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="promotions", description="View promotion history")
@app_commands.describe(roblox_username="Roblox username")
async def promotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    avatar = await get_avatar(roblox_username)
    records = promotion_db.get(roblox_username, [])
    if not records:
        await interaction.followup.send(f"No promotions found for {roblox_username}")
        return

    embed = discord.Embed(
        title=f"Promotion History for {roblox_username}",
        description=f"Total promotions: {len(records)}",
        color=discord.Color.blue()
    )
    if avatar:
        embed.set_thumbnail(url=avatar)

    for i, promo in enumerate(reversed(records[-5:])):
        embed.add_field(
            name=f"Promotion #{len(records) - i}",
            value=f"From: {promo['old_rank']}\nTo: {promo['new_rank']}\nBy: {promo['promoter']}\nOn: {promo['date']}",
            inline=False
        )

    await interaction.followup.send(embed=embed)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
