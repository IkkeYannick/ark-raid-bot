import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()


def get_env_variable(key, as_int=False, required=True, default=None):
    value = os.getenv(key, default)

    if required and value is None:
        raise ValueError(f"{key} not found in .env")

    if as_int and value is not None:
        return int(value)

    return value


# Environment Variables
TOKEN = get_env_variable("DISCORD_TOKEN")
TRIBE_LOG_CHANNEL_ID = get_env_variable("TRIBE_LOG_CHANNEL_ID", as_int=True)
ALERT_CHANNEL_ID = get_env_variable("ALERT_CHANNEL_ID", as_int=True)
TRIBELOG_BOT_ID = get_env_variable("TRIBELOG_BOT_ID", as_int=True)
ROLE_ID = get_env_variable("ROLE_ID", as_int=True)
BASE_MAPS = [
    m.strip().upper()
    for m in get_env_variable("BASE_MAPS", required=False, default="").split(",")
    if m.strip()
]

SCREEN_LOG_REGION = get_env_variable("SCREEN_LOG_REGION", required=False, default="")
SCREEN_LOG_INTERVAL_SECONDS = float(
    get_env_variable("SCREEN_LOG_INTERVAL_SECONDS", required=False, default="10")
)
SCREEN_LOG_OVERLAY = (
    get_env_variable("SCREEN_LOG_OVERLAY", required=False, default="true").lower() == "true"
)
SCREEN_LOG_CHANNEL_ID = get_env_variable(
    "SCREEN_LOG_CHANNEL_ID",
    as_int=True,
    required=False,
)
SCREEN_LOG_DISCORD_TOKEN = get_env_variable(
    "SCREEN_LOG_DISCORD_TOKEN",
    required=False,
)

DEBUG = os.getenv("DEBUG", "false").lower() == "true" or "--debug" in sys.argv


# 🔥 Logging Configuration
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

logger = logging.getLogger("RaidBot")

if DEBUG:
    logger.debug("Debug mode is ENABLED")
