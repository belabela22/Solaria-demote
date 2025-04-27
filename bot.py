import discord
from discord.ext import commands
import os
import threading
from flask import Flask

# Flask app to keep the bot alive on Render
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Start Flask server in a background thread
threading.Thread(target=run_web).start()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True  # Only if you need message content reading
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        print(f"⚠️ Error syncing commands: {e}")

async def load_cogs():
    await bot.load_extension("promote")  # Loads promote.py cog

bot.loop.create_task(load_cogs())

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
