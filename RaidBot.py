print("Starting ARK Raid Bot...")
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
import re
import discord 
from discord.ext import commands
import asyncio
import os

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
DISABLE_SENSOR_ALERTS = os.getenv("DISABLE_SENSOR_ALERTS", "false").lower() == "false"
DISABLE_DESTRUCTION_ALERTS = os.getenv("DISABLE_DESTRUCTION_ALERTS", "false").lower() == "false"
DESTRUCTION_ALERT_THRESHOLD = int(os.getenv("DESTRUCTION_ALERT_THRESHOLD"))
if not DESTRUCTION_ALERT_THRESHOLD:
    DESTRUCTION_ALERT_THRESHOLD = 5
ROLE_ID = int(os.getenv("ROLE_ID"))
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
        print(f"Received message in tribe log: {message.content} from: {message.author}")
        lines = message.content.splitlines()

        for line in lines:
            content = line.upper()
            # Detect the ALERT pattern
            if not DISABLE_SENSOR_ALERTS and "<<ALERT>>" in content:
                print("ALERT detected in message: ", content)
                match1 = re.search(r"\]\[\s*(.*?)\]\s*<<ALERT>>\s*(.*?)\s*<<ALERT>>", content)
                match2 = re.search(r"AN \s*(.*?)\s*\<", content)
                print("Extracted map: ", match1.group(1).strip() if match1 else "No map")
                print("Extracted place: ", match1.group(2).strip() if match1 else "No place found")
                print("Extracted raider: ", match2.group(1).strip() if match2 else "No raider found")

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
                #print("Checking for destruction pattern in message: ", content)
                now = datetime.now()
                counter_reset_time = datetime.now() + timedelta(minutes=30)
                if now > counter_reset_time:
                    destroyed_counter = 0
                    counter_reset_time = now + timedelta(minutes=30)
                destroyed_counter += 1
                #print("DESTRUCTION detected in message: ", content)
                emoji_bar = get_emoji_bar(destroyed_counter)
                if destroyed_counter % 5 == 0:
                    match = re.search(r"\]\[\s*(.*?)\]\s*(.*?)\s*destroyed your\s*'([^']+)'", line)
                    if match:
                        ark_map = match.group(1).strip()
                        destroyed_item = match.group(3).strip()
                        what_destroyed_it = match.group(2).strip()
                    else:
                        destroyed_item = "UNKNOWN ITEM"
                        what_destroyed_it = "UNKNOWN DESTROYER"

                    #print(ark_map)
                    #print(destroyed_item)
                    #print(what_destroyed_it)
                    alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
                    if destroyed_counter >= DESTRUCTION_ALERT_THRESHOLD :
                        #print(destroyed_counter)
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


try:
    bot.run(TOKEN)
except Exception as e:
    print("Bot crashed:", e)
