import os
import asyncio
import logging

from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.config import *
from bot.core import *
from bot.screen_monitor import (
    ScreenRegion,
    ScreenTribeLogMonitor,
    ScreenTribeLogScreenshotMonitor,
    parse_region,
)


logger = logging.getLogger("RaidBot")

# Constants
ALERT_MESSAGE_REPEAT = 3
ALERT_MESSAGE_DELAY = 3
COUNTER_RESET_MINUTES = 30

ROLE_PING = f"<@&{ROLE_ID}>"
ALERT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "alert.png")

# Global state
raid_counter = 0
destroyed_counter = 0
counter_reset_time = datetime.now()
screen_monitor = None
screenshot_monitor = None
screen_region_override = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
    await alert_channel.send("Raid Bot is now online! 🚀")


def get_screen_region() -> ScreenRegion | None:
    if screen_region_override:
        return screen_region_override

    return parse_region(SCREEN_LOG_REGION)


@bot.command(name="screenlog_start")
@commands.has_permissions(manage_guild=True)
async def screenlog_start(ctx, channel: discord.TextChannel = None):
    global screen_monitor

    if screen_monitor and screen_monitor.is_running:
        await ctx.send("Screen tribelog monitor is already running.")
        return

    target_channel = channel or ctx.channel

    try:
        region = get_screen_region()
    except ValueError as exc:
        await ctx.send(f"Could not start screen monitor: {exc}")
        return

    screen_monitor = ScreenTribeLogMonitor(
        channel=target_channel,
        region=region,
        interval_seconds=SCREEN_LOG_INTERVAL_SECONDS,
        show_overlay=SCREEN_LOG_OVERLAY,
        role_mention=ROLE_PING,
    )
    await screen_monitor.start()
    await ctx.send(f"Starting screen tribelog monitor in {target_channel.mention}.")


@bot.command(name="screenlog_stop")
@commands.has_permissions(manage_guild=True)
async def screenlog_stop(ctx):
    global screen_monitor

    if not screen_monitor or not screen_monitor.is_running:
        await ctx.send("Screen tribelog monitor is not running.")
        return

    await screen_monitor.stop()
    await ctx.send("Screen tribelog monitor stopped.")


@bot.command(name="screenlog_screenshot_start")
@commands.has_permissions(manage_guild=True)
async def screenlog_screenshot_start(ctx, channel: discord.TextChannel = None):
    global screenshot_monitor

    if screenshot_monitor and screenshot_monitor.is_running:
        await ctx.send("Screen tribelog screenshot monitor is already running.")
        return

    target_channel = channel or ctx.channel

    try:
        region = get_screen_region()
    except ValueError as exc:
        await ctx.send(f"Could not start screen screenshot monitor: {exc}")
        return

    screenshot_monitor = ScreenTribeLogScreenshotMonitor(
        channel=target_channel,
        region=region,
        interval_seconds=SCREEN_LOG_SCREENSHOT_INTERVAL_SECONDS,
        show_overlay=SCREEN_LOG_OVERLAY,
    )
    await screenshot_monitor.start()
    await ctx.send(f"Starting screen tribelog screenshot monitor in {target_channel.mention}.")


@bot.command(name="screenlog_screenshot_stop")
@commands.has_permissions(manage_guild=True)
async def screenlog_screenshot_stop(ctx):
    global screenshot_monitor

    if not screenshot_monitor or not screenshot_monitor.is_running:
        await ctx.send("Screen tribelog screenshot monitor is not running.")
        return

    await screenshot_monitor.stop()
    await ctx.send("Screen tribelog screenshot monitor stopped.")


@bot.command(name="screenlog_status")
async def screenlog_status(ctx):
    if not screen_monitor or not screen_monitor.is_running:
        await ctx.send("Screen tribelog monitor is not running.")
        return

    region = screen_monitor.region
    if region:
        await ctx.send(
            "Screen tribelog monitor is running at "
            f"`x={region.x}, y={region.y}, w={region.width}, h={region.height}`."
        )
    else:
        await ctx.send("Screen tribelog monitor is starting and detecting the screen size.")


@bot.command(name="screenlog_screenshot_status")
async def screenlog_screenshot_status(ctx):
    if not screenshot_monitor or not screenshot_monitor.is_running:
        await ctx.send("Screen tribelog screenshot monitor is not running.")
        return

    region = screenshot_monitor.region
    if region:
        await ctx.send(
            "Screen tribelog screenshot monitor is running at "
            f"`x={region.x}, y={region.y}, w={region.width}, h={region.height}`."
        )
    else:
        await ctx.send("Screen tribelog screenshot monitor is starting and detecting the screen size.")


@bot.command(name="screenlog_region")
@commands.has_permissions(manage_guild=True)
async def screenlog_region(ctx, x: int, y: int, width: int, height: int):
    global screen_region_override

    if width <= 0 or height <= 0:
        await ctx.send("Width and height must be positive.")
        return

    screen_region_override = ScreenRegion(x=x, y=y, width=width, height=height)
    await ctx.send(
        "Screen tribelog region set to "
        f"`x={x}, y={y}, w={width}, h={height}`. Restart the monitor to use it."
    )


@screenlog_start.error
@screenlog_stop.error
@screenlog_screenshot_start.error
@screenlog_screenshot_stop.error
@screenlog_region.error
async def screenlog_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the `Manage Server` permission to control screen monitoring.")
        return

    raise error


@bot.event
async def on_message(message):
    global raid_counter, destroyed_counter, counter_reset_time

    logger.debug(f"Received message from {message.author} in channel {message.channel.id}")

    if message.author.bot and message.author.id != TRIBELOG_BOT_ID:
        logger.debug("Ignored message from non-tribelog bot.")
        return

    if message.channel.id != TRIBE_LOG_CHANNEL_ID:
        await bot.process_commands(message)
        return

    alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
    lines = message.content.splitlines()

    for line in lines:
        content = line.upper()

        if "<<ALERT>>" in content:
            logger.debug("Raid alert detected.")

            ark_map, location, raider = extract_raid_info(content)

            if not map_is_monitored(ark_map, BASE_MAPS):
                logger.debug(f"Skipped raid for non-monitored map: {ark_map}")
                continue

            if should_reset_counter(counter_reset_time):
                logger.debug("Resetting raid counter.")
                raid_counter = 0
                counter_reset_time = datetime.now() + timedelta(minutes=COUNTER_RESET_MINUTES)

            raid_counter += 1
            logger.debug(f"Raid counter incremented → {raid_counter}")

            emoji_bar = get_emoji_bar(raid_counter)

            await alert_channel.send(
                f"{ROLE_PING} {emoji_bar}\n"
                f"🚨 RAID DETECTED 🚨\n"
                f"MAP: {ark_map}\n"
                f"AT: {location}\n"
                f"BY: {get_raider_emoji(raider)}"
            )
        elif "DESTROYED" in content and not "YOUR TRIBE DESTROYED" in content:
            logger.debug("Destruction event detected.")

            ark_map, destroyer, item = extract_destruction_info(content)

            if not map_is_monitored(ark_map, BASE_MAPS):
                logger.debug(f"Skipped destruction for non-monitored map: {ark_map}")
                continue

            destroyed_counter += 1
            logger.debug(f"Destroyed counter incremented → {destroyed_counter}")

            emoji_bar = get_emoji_bar(destroyed_counter)

            if destroyed_counter >= ALERT_MESSAGE_REPEAT:
                await alert_channel.send(
                    f"{ROLE_PING} {emoji_bar}\n"
                    f"💥 STRUCTURE DESTROYED 💥\n"
                    f"MAP: {ark_map}\n"
                    f"BY: {destroyer}\n"
                    f"ITEM: {item}"
                )

    await bot.process_commands(message)


if __name__ == "__main__":
    logger.info("Starting ARK Raid Bot...")
    bot.run(TOKEN)
