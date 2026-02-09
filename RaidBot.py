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
ROLE_ID = int(os.getenv("ROLE_ID"))
role_ping = f"<@&{ROLE_ID}>"
raid_counter = 0
counter_reset_time = datetime.now() + timedelta(minutes=30)

def get_emoji_bar(count):
    if count < 5:
        return "⚠️"
    elif count < 10:
        return "⚠️⚠️"
    elif count < 20:
        return "⚠️⚠️⚠️"
    elif count < 35:
        return "🔥🔥🔥🔥"
    else:
        return "💀💀💀💀💀💀"

now = datetime.now()
if now > counter_reset_time:
    raid_counter = 0
    counter_reset_time = now + timedelta(minutes=30)

raid_counter += 1
emoji_bar = get_emoji_bar(raid_counter)

KEYWORD = "<<ALERT>>"

file_path = os.path.join(os.path.dirname(__file__), "alert.png")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    global raid_counter, counter_reset_time
    if message.author.bot and message.author.id != TRIBELOG_BOT_ID:
        return

    if message.channel.id == TRIBE_LOG_CHANNEL_ID:
        print(f"Received message in tribe log: {message.content} from: {message.author}")
        content = message.content.upper()

        # Detect the ALERT pattern
        if "<<ALERT>>" in content:
            print("ALERT detected in message: ", message.content)
            match1 = re.search(r"<<ALERT>>\s*(.*?)\s*<<ALERT>>", message.content)
            match2 = re.search(r"by an \s*(.*?)\s*<", message.content)
            print("Extracted place: ", match1.group(1).strip() if match1 else "No place found")
            print("Extracted raider: ", match2.group(1).strip() if match2 else "No raider found")

            if match1:
                place = match1.group(1).strip()
            else:
                place = "UNKNOWN LOCATION"

            if match2:
                raider = match2.group(1).strip()
            else:
                raider = "UNKNOWN RAIDER"

            if raider == "enemy dino":
                raider_emoji = "Enemy Dino 🦖"
            elif raider == "enemy player":
                raider_emoji = "Enemy Player 👤"
            else:
                raider_emoji = "What the fuck is this❓"

            alert_channel = bot.get_channel(ALERT_CHANNEL_ID)

            for i in range(3):
                await alert_channel.send(
                    content=(
                        f"{role_ping} {emoji_bar}\n"
                        f"🚨 **RAID DETECTED** 🚨\n"
                        f"AT: {place}\n"
                        f"BY: {raider_emoji}\n"
                        f"Raid count (30m): {raid_counter}"
                    ),
                    file=discord.File(file_path)
                )
                await asyncio.sleep(3)

    await bot.process_commands(message)


try:
    bot.run(TOKEN)
except Exception as e:
    print("Bot crashed:", e)
