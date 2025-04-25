import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask

# Flask app for port binding (Render requirement)
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

# Promotion and Demotion databases
promotion_db = {}
demotion_db = {}

# Define the cooldowns for each role transition
cooldowns = {
    ("El3", "El4"): datetime.timedelta(hours=2),
    ("El4", "El5"): datetime.timedelta(hours=12),
    ("El5", "El6"): datetime.timedelta(hours=0),
    ("El6", "El7"): datetime.timedelta(days=2),
    ("El7", "El8"): datetime.timedelta(days=3),
    ("El8", "El9"): datetime.timedelta(days=5),
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
    roblox_username="The Roblox username of the user to promote",
    current_rank="The user's current rank",
    new_rank="The new rank after promotion"
)
async def promote(interaction: discord.Interaction, roblox_username: str, current_rank: str, new_rank: str):
    await interaction.response.defer()

    # Check if the promotion transition exists in cooldowns
    if (current_rank, new_rank) in cooldowns:
        required_cooldown = cooldowns[(current_rank, new_rank)]
        now = datetime.datetime.now()

        # Check if the user has been promoted before and if the cooldown has expired
        if roblox_username in promotion_db:
            last_promotion = promotion_db[roblox_username].get('last_promotion', None)
            if last_promotion:
                last_promotion_time = datetime.datetime.strptime(last_promotion, "%Y-%m-%d %H:%M:%S")
                time_diff = now - last_promotion_time

                if time_diff < required_cooldown:
                    remaining_time = required_cooldown - time_diff
                    remaining_time_str = str(remaining_time).split('.')[0]  # Remove microseconds
                    await interaction.followup.send(f"{roblox_username} cannot be promoted yet. Please wait {remaining_time_str} before promoting again.")
                    return

        # Proceed with promotion and update promotion time
        promotion_entry = {
            "current_rank": current_rank,
            "new_rank": new_rank,
            "date": now.strftime("%Y-%m-%d %H:%M:%S"),
            "last_promotion": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

        promotion_db[roblox_username] = promotion_entry

        # Send success message with avatar
        avatar_url = await get_roblox_avatar(roblox_username)
        embed = discord.Embed(
            title=f"🎉 Promotion for {roblox_username}",
            color=discord.Color.green()
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="Previous Rank", value=current_rank, inline=True)
        embed.add_field(name="New Rank", value=new_rank, inline=True)
        embed.add_field(name="Date", value=now.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="demote", description="Demote a Roblox user")
@app_commands.describe(
    roblox_username="The Roblox username of the user to demote",
    current_rank="The user's current rank before demotion",
    demoted_rank="The new lower rank after demotion",
    reason="The reason for the demotion"
)
async def demote(interaction: discord.Interaction, roblox_username: str, current_rank: str, demoted_rank: str, reason: str):
    await interaction.response.defer()
    
    # Ensure the reason is provided
    if not reason:
        await interaction.followup.send("You must provide a reason for the demotion.")
        return
    
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    demoter = interaction.user.name

    # Check if there is a promotion history for the user and remove the last one
    if roblox_username in promotion_db and promotion_db.get(roblox_username):
        promotion_db[roblox_username].pop()  # Remove the last promotion

    demotion_entry = {
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
        "reason": reason,
        "date": current_date,
        "demoter": demoter
    }

    if roblox_username not in demotion_db:
        demotion_db[roblox_username] = []
    demotion_db[roblox_username].append(demotion_entry)

    avatar_url = await get_roblox_avatar(roblox_username)

    embed = discord.Embed(
        title=f"⚠️ Demotion for {roblox_username}",
        color=discord.Color.orange()
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="Previous Rank", value=current_rank, inline=True)
    embed.add_field(name="New Rank", value=demoted_rank, inline=True)
    embed.add_field(name="Demoted By", value=demoter, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Date", value=current_date, inline=False)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="promotions", description="Show the promotion history of a Roblox user")
@app_commands.describe(roblox_username="The Roblox username of the user to see promotion history")
async def promotions(interaction: discord.Interaction, roblox_username: str = None):
    if roblox_username is None:
        # Show all promotions
        if not promotion_db:
            await interaction.response.send_message("No promotions found.")
            return
        embed = discord.Embed(
            title="All Promotions",
            color=discord.Color.blue()
        )
        for username, data in promotion_db.items():
            embed.add_field(
                name=f"Promotion for {username}",
                value=f"From {data['current_rank']} to {data['new_rank']} on {data['date']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)
    else:
        # Show a specific user's promotions
        if roblox_username in promotion_db:
            data = promotion_db[roblox_username]
            embed = discord.Embed(
                title=f"Promotion History for {roblox_username}",
                color=discord.Color.green()
            )
            embed.add_field(name="Previous Rank", value=data["current_rank"], inline=True)
            embed.add_field(name="New Rank", value=data["new_rank"], inline=True)
            embed.add_field(name="Date", value=data["date"], inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"No promotion history found for {roblox_username}.")

@bot.tree.command(name="demotions", description="Show the demotion history of a Roblox user")
@app_commands.describe(roblox_username="The Roblox username of the user to see demotion history")
async def demotions(interaction: discord.Interaction, roblox_username: str = None):
    if roblox_username is None:
        # Show all demotions
        if not demotion_db:
            await interaction.response.send_message("No demotions found.")
            return
        embed = discord.Embed(
            title="All Demotions",
            color=discord.Color.red()
        )
        for username, data in demotion_db.items():
            for demotion in data:
                embed.add_field(
                    name=f"Demotion for {username}",
                    value=f"From {demotion['current_rank']}
