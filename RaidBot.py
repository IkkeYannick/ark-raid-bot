import os
import sys
import re
import asyncio
import traceback
from datetime import datetime, timedelta

from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

def get_env_variable(key, as_int=False, required=True):
    """Retrieve and validate environment variables."""
    value = os.getenv(key)
    if required and not value:
        raise ValueError(f"{key} not found in .env")
    if as_int and value:
        return int(value)
    return value

# Environment Configuration
TOKEN = get_env_variable("DISCORD_TOKEN", required=True)
TRIBE_LOG_CHANNEL_ID = get_env_variable("TRIBE_LOG_CHANNEL_ID", as_int=True)
ALERT_CHANNEL_ID = get_env_variable("ALERT_CHANNEL_ID", as_int=True)
TRIBELOG_BOT_ID = get_env_variable("TRIBELOG_BOT_ID", as_int=True)
ROLE_ID = get_env_variable("ROLE_ID", as_int=True)
DISABLE_SENSOR_ALERTS = os.getenv("DISABLE_SENSOR_ALERTS", "false").lower() == "true"
DISABLE_DESTRUCTION_ALERTS = os.getenv("DISABLE_DESTRUCTION_ALERTS", "false").lower() == "true"
DESTRUCTION_ALERT_THRESHOLD = int(os.getenv("DESTRUCTION_ALERT_THRESHOLD", "5"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true" or "--debug" in sys.argv

# Constants
ALERT_MESSAGE_REPEAT = 3
DESTRUCTION_IMAGE_THRESHOLD = 15
COUNTER_RESET_MINUTES = 30
ALERT_MESSAGE_DELAY = 3
RAIDER_EMOJI_MAP = {
    "ENEMY DINO": "Enemy Dino 🦖",
    "ENEMY SURVIVOR": "Enemy Player 👤",
}
ALERT_REGEX = r"\]\[\s*(.*?)\]\s*<<ALERT>>\s*(.*?)\s*<<ALERT>>"
RAIDER_REGEX = r"AN \s*(.*?)\s*\<"
DESTRUCTION_REGEX = r"\]\[\s*(.*?)\]\s*(.*?)\s*destroyed your\s*'([^']+)'"

ROLE_PING = f"<@&{ROLE_ID}>"
ALERT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "alert.png")

# Global state
raid_counter = 0
destroyed_counter = 0
counter_reset_time = datetime.now()


def print_config():
    """Print bot configuration."""
    print("="*50)
    print("ARK Raid Bot Configuration")
    print("="*50)
    print(f"Sensor Alerts: {'ENABLED' if not DISABLE_SENSOR_ALERTS else 'DISABLED'}")
    print(f"Destruction Alerts: {'ENABLED' if not DISABLE_DESTRUCTION_ALERTS else 'DISABLED'}")
    print(f"Destruction Alert Threshold: {DESTRUCTION_ALERT_THRESHOLD} items")
    print(f"Debug Mode: {'ENABLED' if DEBUG else 'DISABLED'}")
    if DEBUG:
        print(f"Alert Channel ID: {ALERT_CHANNEL_ID}")
        print(f"Tribe Log Channel ID: {TRIBE_LOG_CHANNEL_ID}")
    print("="*50 + "\n")


print_config()

def get_emoji_bar(count: int) -> str:
    """Get danger level emoji bar based on count."""
    if count < 5:
        return "⚠️⚠️⚠️"
    elif count < 10:
        return "🔥🔥🔥🔥🔥🔥🔥🔥"
    else:
        return "💀💀💀💀💀💀"


def should_reset_counter(reset_time: datetime) -> bool:
    """Check if counter should be reset."""
    return datetime.now() > reset_time


def get_raider_emoji(raider: str) -> str:
    """Get emoji representation for raider type."""
    return RAIDER_EMOJI_MAP.get(raider, "Unknown Raider ❓")


def extract_raid_info(content: str) -> tuple:
    """Extract map and location from raid alert message."""
    match_alert = re.search(ALERT_REGEX, content)
    match_raider = re.search(RAIDER_REGEX, content)
    
    ark_map = match_alert.group(1).strip() if match_alert else "UNKNOWN MAP"
    location = match_alert.group(2).strip() if match_alert else "UNKNOWN LOCATION"
    raider = match_raider.group(1).strip() if match_raider else "UNKNOWN RAIDER"
    
    return ark_map, location, raider


def extract_destruction_info(line: str) -> tuple:
    """Extract map, item, and destroyer from destruction message."""
    match = re.search(DESTRUCTION_REGEX, line)
    
    if match:
        ark_map = match.group(1).strip()
        destroyer = match.group(2).strip()
        item = match.group(3).strip()
    else:
        ark_map = "UNKNOWN MAP"
        destroyer = "UNKNOWN DESTROYER"
        item = "UNKNOWN ITEM"
    
    return ark_map, destroyer, item

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if DISABLE_DESTRUCTION_ALERTS and DISABLE_SENSOR_ALERTS:
        print("WARNING: Both sensor and destruction alerts are disabled. The bot will not send any alerts.")
        await bot.close()

async def send_raid_alert(alert_channel, ark_map: str, location: str, raider: str, emoji_bar: str):
    """Send raid alert message multiple times."""
    raider_emoji = get_raider_emoji(raider)
    message_content = (
        f"{ROLE_PING} {emoji_bar}\n"
        f"🚨 **RAID DETECTED** 🚨\n"
        f"MAP: {ark_map}\n"
        f"AT: {location}\n"
        f"BY: {raider_emoji}\n"
        f"Raid count (30m): {raid_counter}"
    )
    
    for _ in range(ALERT_MESSAGE_REPEAT):
        await alert_channel.send(content=message_content, file=discord.File(ALERT_IMAGE_PATH))
        await asyncio.sleep(ALERT_MESSAGE_DELAY)


async def send_destruction_alert(alert_channel, ark_map: str, destroyer: str, item: str, emoji_bar: str):
    """Send destruction alert message."""
    has_image = destroyed_counter >= DESTRUCTION_IMAGE_THRESHOLD
    message_content = (
        f"{ROLE_PING} {emoji_bar}\n"
        f"💥 **CLEARING SPAMM** 💥\n"
        f"MAP: {ark_map}\n"
        f"ITEM: {item}\n"
        f"BY: {destroyer}\n"
        f"Destruction count (30m): {destroyed_counter}"
    )
    
    await alert_channel.send(
        content=message_content,
        file=discord.File(ALERT_IMAGE_PATH) if has_image else None
    )


@bot.event
async def on_message(message):
    global raid_counter, counter_reset_time, destroyed_counter
    
    # Ignore non-tribelog bots
    if message.author.bot and message.author.id != TRIBELOG_BOT_ID:
        return

    if message.channel.id != TRIBE_LOG_CHANNEL_ID:
        await bot.process_commands(message)
        return

    if DEBUG:
        print(f"Received message from: {message.author}")

    alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
    lines = message.content.splitlines()

    for line in lines:
        content = line.upper()
        
        # Handle raid alerts
        if not DISABLE_SENSOR_ALERTS and "<<ALERT>>" in content:
            if DEBUG:
                print("ALERT detected")
            
            if should_reset_counter(counter_reset_time):
                raid_counter = 0
                counter_reset_time = datetime.now() + timedelta(minutes=COUNTER_RESET_MINUTES)
            
            raid_counter += 1
            ark_map, location, raider = extract_raid_info(content)
            
            if DEBUG:
                print(f"  Map: {ark_map}")
                print(f"  Location: {location}")
                print(f"  Raider: {raider}")
            
            emoji_bar = get_emoji_bar(raid_counter)
            await send_raid_alert(alert_channel, ark_map, location, raider, emoji_bar)
        
        # Handle destruction alerts
        elif not DISABLE_DESTRUCTION_ALERTS and "DESTROYED YOUR" in content:
            if DEBUG:
                print("DESTRUCTION detected")
            
            if should_reset_counter(counter_reset_time):
                destroyed_counter = 0
                counter_reset_time = datetime.now() + timedelta(minutes=COUNTER_RESET_MINUTES)
            
            destroyed_counter += 1
            
            if destroyed_counter % DESTRUCTION_ALERT_THRESHOLD == 0:
                ark_map, destroyer, item = extract_destruction_info(line)
                
                if DEBUG:
                    print(f"  Map: {ark_map}")
                    print(f"  Item: {item}")
                    print(f"  Destroyed by: {destroyer}")
                    print(f"  Destruction count: {destroyed_counter}")
                
                emoji_bar = get_emoji_bar(destroyed_counter)
                await send_destruction_alert(alert_channel, ark_map, destroyer, item, emoji_bar)

    await bot.process_commands(message)


if __name__ == "__main__":
    try:
        print("Starting ARK Raid Bot...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"Bot encountered an error: {e}")
        if DEBUG:
            traceback.print_exc()
