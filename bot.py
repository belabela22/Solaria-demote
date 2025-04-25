import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import os
import threading
from flask import Flask

# Flask app for keeping Render happy (port binding)
app = Flask(__name__)

@app.route('/')
def home():
    return "Demotion bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Database to store demotion history
demotion_db = {}  # Format: {roblox_username: List[demotion_entries]}

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

@bot.tree.command(name="demote", description="Demote a Roblox user")
@app_commands.describe(
    roblox_username="The Roblox username of the user to demote",
    demoted_rank="The new lower rank after demotion",
    current_rank="The user's current rank before demotion"
)
async def demote(interaction: discord.Interaction, roblox_username: str, demoted_rank: str, current_rank: str):
    await interaction.response.defer()
    
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    demoter = interaction.user.name

    demotion_entry = {
        "current_rank": current_rank,
        "demoted_rank": demoted_rank,
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

    embed.add_field(name="Current Rank", value=current_rank, inline=True)
    embed.add_field(name="Demoted Rank", value=demoted_rank, inline=True)
    embed.add_field(name="Demoted By", value=demoter, inline=False)
    embed.add_field(name="Date", value=current_date, inline=False)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="demotions", description="View demotion history for a Roblox user")
@app_commands.describe(
    roblox_username="The Roblox username to check demotion history for"
)
async def demotions(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()

    avatar_url = await get_roblox_avatar(roblox_username)

    if roblox_username not in demotion_db or not demotion_db[roblox_username]:
        embed = discord.Embed(
            title=f"No demotions found for {roblox_username}",
            color=discord.Color.red()
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        await interaction.followup.send(embed=embed)
        return

    user_demotions = demotion_db[roblox_username]

    embed = discord.Embed(
        title=f"📉 Demotion History for {roblox_username}",
        description=f"Total demotions: {len(user_demotions)}",
        color=discord.Color.blue()
    )

    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    for i, dem in enumerate(reversed(user_demotions[-5:])):
        embed.add_field(
            name=f"Demotion #{len(user_demotions) - i}",
            value=f"**From:** {dem['current_rank']}\n**To:** {dem['demoted_rank']}\n**By:** {dem['demoter']}\n**On:** {dem['date']}",
            inline=False
        )

    if len(user_demotions) > 5:
        embed.set_footer(text=f"Showing latest 5 of {len(user_demotions)} demotions")

    await interaction.followup.send(embed=embed)

# Start bot with token from environment variable
bot.run(os.getenv("DISCORD_TOKEN"))
