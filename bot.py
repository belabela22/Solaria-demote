import discord
from discord import app_commands
import datetime

promotion_db = {}  # User cooldowns: roblox_username -> cooldown_end_time

class Promote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="promote", description="Promote a Roblox user to a new rank.")
    @app_commands.describe(roblox_username="The Roblox username",
                            old_rank="Current rank of the user",
                            new_rank="New rank after promotion",
                            cooldown="Cooldown time in hours (use 0 for instant promotion)")
    async def promote(self, interaction: discord.Interaction, roblox_username: str, old_rank: str, new_rank: str, cooldown: float):
        
        now = datetime.datetime.utcnow()

        # Check if user is still on cooldown
        if roblox_username in promotion_db:
            cooldown_end = promotion_db[roblox_username]
            if now < cooldown_end:
                # Cooldown active
                timestamp = int(cooldown_end.timestamp())
                await interaction.response.send_message(
                    f"❌ {roblox_username} is still on cooldown! Please wait until <t:{timestamp}:R>.", ephemeral=True)
                return

        # Calculate cooldown
        if cooldown > 0:
            cooldown_end_time = now + datetime.timedelta(hours=cooldown)
            promotion_db[roblox_username] = cooldown_end_time
        else:
            promotion_db.pop(roblox_username, None)  # No cooldown needed

        # Create fancy embed
        embed = discord.Embed(
            title="Promotion Successful!",
            color=discord.Color.green()
        )
        embed.add_field(name="Roblox User", value=roblox_username, inline=True)
        embed.add_field(name="Old Rank", value=old_rank, inline=True)
        embed.add_field(name="New Rank", value=new_rank, inline=True)
        
        if cooldown > 0:
            timestamp = int((now + datetime.timedelta(hours=cooldown)).timestamp())
            embed.add_field(name="Next Promotion Available", value=f"<t:{timestamp}:R>", inline=False)
        else:
            embed.add_field(name="Next Promotion Available", value="Immediate (No cooldown)", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Promote(bot))
# Run bot
bot.run(os.getenv("DISCORD_TOKEN"))
