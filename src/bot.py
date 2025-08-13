import os
import logging
import discord
from discord.ext import commands
from core.container_pool import ContainerPool
from services.docker_service import DockerService
from services.kivy_validator import KivyValidator
from services.code_processor import CodeProcessor

# Load environment variables
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup logging
logging.basicConfig(level=logging.INFO)

# Initialize the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize services
container_pool = ContainerPool()
docker_service = DockerService()
kivy_validator = KivyValidator()
code_processor = CodeProcessor()

@bot.event
async def on_ready():
    logging.info(f"✅ Bot {bot.user} is online!")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # Process the message for Kivy code
    # (Implementation for extracting and validating Kivy code goes here)

    await bot.process_commands(message)

@bot.command()
async def ping(ctx: commands.Context):
    await ctx.send("🏓 Pong!")

if __name__ == "__main__":
    bot.run(TOKEN)