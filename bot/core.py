import re
import logging
from datetime import datetime

logger = logging.getLogger("RaidBot")

# Regex patterns
ALERT_REGEX = r"\]\[\s*(.*?)\]\s*<<ALERT>>\s*(.*?)\s*<<ALERT>>"
RAIDER_REGEX = r"AN\s*(.*?)\s*\<"
DESTRUCTION_REGEX_WITH_OWNER = r"\[\d{1,2}-\d{1,2}\s\d{1,2}:\d{2}:\d{2}\]\[\s*(.*?)\]\s*(.*?)\s*destroyed your\s*'([^']+)'"
DESTRUCTION_REGEX_NO_OWNER = r"\[\d{1,2}-\d{1,2}\s\d{1,2}:\d{2}:\d{2}\]\[\s*(.*?)\] Your\s*'([^']+)' was destroyed!"

RAIDER_EMOJI_MAP = {
    "ENEMY DINO": "Enemy Dino 🦖",
    "ENEMY SURVIVOR": "Enemy Player 👤",
}


def map_is_monitored(ark_map: str, base_maps: list[str]) -> bool:
    monitored = not base_maps or ark_map.strip().upper() in [m.upper() for m in base_maps]
    logger.debug(f"Map check → {ark_map} monitored={monitored}")
    return monitored


def get_emoji_bar(count: int) -> str:
    if count < 5:
        result = "⚠️⚠️⚠️"
    elif count < 10:
        result = "🔥🔥🔥🔥🔥🔥🔥🔥"
    else:
        result = "💀💀💀💀💀💀"

    logger.debug(f"Emoji bar for count={count}: {result}")
    return result


def should_reset_counter(reset_time: datetime) -> bool:
    result = datetime.now() > reset_time
    logger.debug(f"Counter reset check → now > {reset_time} ? {result}")
    return result


def get_raider_emoji(raider: str) -> str:
    result = RAIDER_EMOJI_MAP.get(raider, "Unknown Raider ❓")
    logger.debug(f"Raider emoji lookup → {raider} → {result}")
    return result


def extract_raid_info(content: str) -> tuple:
    match_alert = re.search(ALERT_REGEX, content)
    match_raider = re.search(RAIDER_REGEX, content)

    ark_map = match_alert.group(1).strip() if match_alert else "UNKNOWN MAP"
    location = match_alert.group(2).strip() if match_alert else "UNKNOWN LOCATION"
    raider = match_raider.group(1).strip() if match_raider else "UNKNOWN RAIDER"

    logger.debug(f"Extracted raid info → map={ark_map}, location={location}, raider={raider}")
    return ark_map, location, raider


def extract_destruction_info(line: str) -> tuple:
    owner_match = re.search(DESTRUCTION_REGEX_WITH_OWNER, line)
    no_owner_match = re.search(DESTRUCTION_REGEX_NO_OWNER, line)

    if owner_match:
        ark_map = owner_match.group(1).strip()
        destroyer = owner_match.group(2).strip()
        item = owner_match.group(3).strip()
    elif no_owner_match:
        ark_map = no_owner_match.group(1).strip()
        destroyer = "No destroyed found"
        item = no_owner_match.group(2).strip()
    else:
        ark_map = "UNKNOWN MAP"
        destroyer = "UNKNOWN DESTROYER"
        item = "UNKNOWN ITEM"

    logger.debug(f"Extracted destruction → map={ark_map}, destroyer={destroyer}, item={item}")
    return ark_map, destroyer, item