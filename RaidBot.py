from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
import re
import discord 
from discord.ext import commands
import asyncio
import os
import sys

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in .env")

TRIBE_LOG_CHANNEL_ID = int(os.getenv("TRIBE_LOG_CHANNEL_ID"))
if not TRIBE_LOG_CHANNEL_ID:
    raise ValueError("TRIBE_LOG_CHANNEL_ID not found in .env")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
if not ALERT_CHANNEL_ID:
    raise ValueError("ALERT_CHANNEL_ID not found in .env")
TRIBELOG_BOT_ID = int(os.getenv("TRIBELOG_BOT_ID"))
if not TRIBELOG_BOT_ID:
    raise ValueError("TRIBELOG_BOT_ID not found in .env")
DISABLE_SENSOR_ALERTS = os.getenv("DISABLE_SENSOR_ALERTS", "false").lower() == "true"
DISABLE_DESTRUCTION_ALERTS = os.getenv("DISABLE_DESTRUCTION_ALERTS", "false").lower() == "true"
DESTRUCTION_ALERT_THRESHOLD = (int(os.getenv("DESTRUCTION_ALERT_THRESHOLD"))) if os.getenv("DESTRUCTION_ALERT_THRESHOLD") else 5
ROLE_ID = int(os.getenv("ROLE_ID"))
DEBUG = (os.getenv("DEBUG", "false").lower() == "true") or ("--debug" in sys.argv)

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
role_ping = f"<@&{ROLE_ID}>"
raid_counter = 0
destroyed_counter = 0

def get_emoji_bar(count):
    if count < 5:
        return "⚠️⚠️⚠️"
    elif count < 10:
        return "🔥🔥🔥🔥🔥🔥🔥🔥"
    else:
        return "💀💀💀💀💀💀"

file_path = os.path.join(os.path.dirname(__file__), "alert.png")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if DISABLE_DESTRUCTION_ALERTS and DISABLE_SENSOR_ALERTS:
        print("WARNING: Both sensor and destruction alerts are disabled. The bot will not send any alerts.")
        await bot.close()

@bot.event
async def on_message(message):
    global raid_counter, counter_reset_time, destroyed_counter
    if message.author.bot and message.author.id != TRIBELOG_BOT_ID:
        return

    if message.channel.id == TRIBE_LOG_CHANNEL_ID:
        if DEBUG:
            print(f"Received message in tribe log from: {message.author}")
        lines = message.content.splitlines()

        for line in lines:
            content = line.upper()
            # Detect the ALERT pattern
            if not DISABLE_SENSOR_ALERTS and "<<ALERT>>" in content:
                if DEBUG:
                    print("ALERT detected in message")
                match1 = re.search(r"\]\[\s*(.*?)\]\s*<<ALERT>>\s*(.*?)\s*<<ALERT>>", content)
                match2 = re.search(r"AN \s*(.*?)\s*\<", content)
                if DEBUG:
                    print(f"  Map: {match1.group(1).strip() if match1 else 'No map'}")
                    print(f"  Location: {match1.group(2).strip() if match1 else 'No location'}")
                    print(f"  Raider: {match2.group(1).strip() if match2 else 'No raider'}")

                if match2:
                    raider = match2.group(1).strip()
                else:
                    raider = "UNKNOWN RAIDER"

                if raider == "ENEMY DINO":
                    raider_emoji = "Enemy Dino 🦖"
                elif raider == "ENEMY SURVIVOR":
                    raider_emoji = "Enemy Player 👤"
                else:
                    raider_emoji = "What the fuck is this❓"

                alert_channel = bot.get_channel(ALERT_CHANNEL_ID)

                now = datetime.now()
                counter_reset_time = datetime.now() + timedelta(minutes=30)
                if now > counter_reset_time:
                    raid_counter = 0
                    counter_reset_time = now + timedelta(minutes=30)

                raid_counter += 1
                emoji_bar = get_emoji_bar(raid_counter)

                for i in range(3):
                    await alert_channel.send(
                        content=(
                            f"{role_ping} {emoji_bar}\n"
                            f"🚨 **RAID DETECTED** 🚨\n"
                            f"MAP: {match1.group(1).strip() if match1 else 'UNKNOWN MAP'}\n"
                            f"AT: {match1.group(2).strip() if match1 else 'UNKNOWN LOCATION'}\n"
                            f"BY: {raider_emoji}\n"
                            f"Raid count (30m): {raid_counter}"
                        ),
                        file=discord.File(file_path)
                    )
                    await asyncio.sleep(3)
            elif not DISABLE_DESTRUCTION_ALERTS and "DESTROYED YOUR" in content :
                if DEBUG:
                    print("DESTRUCTION detected in message")
                now = datetime.now()
                counter_reset_time = datetime.now() + timedelta(minutes=30)
                if now > counter_reset_time:
                    destroyed_counter = 0
                    counter_reset_time = now + timedelta(minutes=30)
                destroyed_counter += 1
                emoji_bar = get_emoji_bar(destroyed_counter)
                if destroyed_counter % DESTRUCTION_ALERT_THRESHOLD == 0:
                    match = re.search(r"\]\[\s*(.*?)\]\s*(.*?)\s*destroyed your\s*'([^']+)'", line)
                    if match:
                        ark_map = match.group(1).strip()
                        destroyed_item = match.group(3).strip()
                        what_destroyed_it = match.group(2).strip()
                    else:
                        destroyed_item = "UNKNOWN ITEM"
                        what_destroyed_it = "UNKNOWN DESTROYER"

                    if DEBUG:
                        print(f"  Map: {ark_map}")
                        print(f"  Item: {destroyed_item}")
                        print(f"  Destroyed by: {what_destroyed_it}")
                    alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
                    if DEBUG:
                        print(f"  Destruction count: {destroyed_counter}")
                    await alert_channel.send(
                            content=(
                                f"{role_ping} {emoji_bar}\n"
                                f"💥 **CLEARING SPAMM** 💥\n"
                                f"MAP: {ark_map}"
                                f"ITEM: {destroyed_item}\n"
                                f"BY: {what_destroyed_it}\n"
                                f"Destruction count (30m): {destroyed_counter}"
                            ),
                            file=discord.File(file_path) if destroyed_counter >= 15 else None
                        )

    await bot.process_commands(message)


if __name__ == "__main__":
    try:
        print("Starting ARK Raid Bot...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"Bot encountered an error: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()
