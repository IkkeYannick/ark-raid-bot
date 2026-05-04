import asyncio
import logging

import discord

from bot.config import (
    DEBUG,
    SCREEN_LOG_CHANNEL_ID,
    SCREEN_LOG_DISCORD_TOKEN,
    SCREEN_LOG_INTERVAL_SECONDS,
    SCREEN_LOG_OVERLAY,
    SCREEN_LOG_REGION,
    ROLE_ID,
)
from bot.screen_monitor import ScreenTribeLogMonitor, parse_region


logger = logging.getLogger("RaidBot.screen_monitor_runner")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
screen_monitor: ScreenTribeLogMonitor | None = None


@client.event
async def on_ready():
    global screen_monitor

    logger.info("Logged in as %s. Starting standalone screen monitor.", client.user)

    if screen_monitor and screen_monitor.is_running:
        logger.debug("Standalone screen monitor is already running.")
        return

    channel = client.get_channel(SCREEN_LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(SCREEN_LOG_CHANNEL_ID)
        except discord.DiscordException:
            logger.exception("Could not find SCREEN_LOG_CHANNEL_ID=%s", SCREEN_LOG_CHANNEL_ID)
            await client.close()
            return

    try:
        region = parse_region(SCREEN_LOG_REGION)
    except ValueError:
        logger.exception("Invalid SCREEN_LOG_REGION.")
        await client.close()
        return

    screen_monitor = ScreenTribeLogMonitor(
        channel=channel,
        region=region,
        interval_seconds=SCREEN_LOG_INTERVAL_SECONDS,
        show_overlay=SCREEN_LOG_OVERLAY,
        role_mention=f"<@&{ROLE_ID}>",
    )
    await screen_monitor.start()


async def main() -> None:
    try:
        await client.start(SCREEN_LOG_DISCORD_TOKEN)
    finally:
        if screen_monitor and screen_monitor.is_running:
            await screen_monitor.stop()


if __name__ == "__main__":
    logger.info("Starting standalone ARK screen tribelog monitor...")
    if DEBUG:
        logger.debug("Standalone screen monitor debug mode is ENABLED")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Standalone screen monitor stopped.")
