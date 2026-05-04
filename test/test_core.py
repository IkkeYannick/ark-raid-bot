import pytest
from datetime import datetime, timedelta

from bot.core import (
    map_is_monitored,
    get_emoji_bar,
    should_reset_counter,
    get_raider_emoji,
    extract_raid_info,
    extract_destruction_info
)
from bot.screen_monitor import (
    ScreenRegion,
    clean_ocr_text,
    default_tribelog_region,
    has_destroyed_structure_alert,
    merge_cleaned_ocr_lines,
    new_lines_since_last_scan,
    parse_region,
    prepare_ocr_images,
    resolve_tesseract_cmd,
)


def test_get_emoji_bar_low():
    result = get_emoji_bar(2)
    assert result == "⚠️⚠️⚠️", \
        f"For count=2 expected 3 warning emojis but got: {result}"


def test_get_emoji_bar_medium():
    result = get_emoji_bar(7)
    assert result == "🔥🔥🔥🔥🔥🔥🔥🔥", \
        f"For count=7 expected 8 fire emojis but got: {result}"


def test_get_emoji_bar_high():
    result = get_emoji_bar(15)
    assert result == "💀💀💀💀💀💀", \
        f"For count=15 expected 6 skull emojis but got: {result}"


def test_should_reset_counter_true():
    past_time = datetime.now() - timedelta(minutes=1)
    result = should_reset_counter(past_time)
    assert result is True, \
        f"Counter should reset for past time {past_time}, but returned {result}"


def test_should_reset_counter_false():
    future_time = datetime.now() + timedelta(minutes=10)
    result = should_reset_counter(future_time)
    assert result is False, \
        f"Counter should NOT reset for future time {future_time}, but returned {result}"


def test_get_raider_emoji_known():
    result = get_raider_emoji("ENEMY DINO")
    assert result == "Enemy Dino 🦖", \
        f"Expected 'Enemy Dino 🦖' but got: {result}"


def test_get_raider_emoji_unknown():
    result = get_raider_emoji("ALIEN")
    assert result == "Unknown Raider ❓", \
        f"Unknown raider should return default message, but got: {result}"


def test_extract_raid_info():
    message = "[12:00][TheIsland] <<ALERT>> Base 123 <<ALERT>> AN ENEMY DINO <"
    ark_map, location, raider = extract_raid_info(message)

    assert ark_map == "TheIsland", \
        f"Expected map 'TheIsland' but got: {ark_map}"

    assert location == "Base 123", \
        f"Expected location 'Base 123' but got: {location}"

    assert raider == "ENEMY DINO", \
        f"Expected raider 'ENEMY DINO' but got: {raider}"


def test_extract_destruction_info_with_owner():
    line = "[2-24 7:48:25][TheIsland] 999 - Lvl 120 (999) destroyed your 'Metal Floor'!"
    ark_map, destroyer, item = extract_destruction_info(line)

    assert ark_map == "TheIsland", \
        f"Expected map 'TheIsland' but got: {ark_map}"

    assert destroyer == "999 - Lvl 120 (999)", \
        f"Expected destroyer '999 - Lvl 120 (999)' but got: {destroyer}"

    assert item == "Metal Floor", \
        f"Expected item 'Metal Floor' but got: {item}"
    

def test_extract_destruction_info_no_owner():
    line = "[2-24 7:49:54][Ragnarok] Your 'Kav Thatch Foundation' was destroyed!"
    ark_map, destroyer, item = extract_destruction_info(line)

    assert ark_map == "Ragnarok", \
        f"Expected map 'Ragnarok' but got: {ark_map}"

    assert destroyer == "No destroyed found", \
        f"Expected destroyer 'No destroyed found' but got: {destroyer}"

    assert item == "Kav Thatch Foundation", \
        f"Expected item 'Kav Thatch Foundation' but got: {item}"


def test_parse_region():
    assert parse_region("760,210,420,660") == ScreenRegion(760, 210, 420, 660)


def test_default_tribelog_region_is_centered():
    region = default_tribelog_region(1920, 1080)

    assert region == ScreenRegion(749, 205, 422, 669)


def test_clean_ocr_text_removes_noise():
    lines = clean_ocr_text("  Day 12, 16:13: Your wall was destroyed!  \n||\nabc\n")

    assert lines == ["Day 12, 16:13: Your wall was destroyed!"]


def test_prepare_ocr_images_turns_red_text_dark_for_tesseract():
    Image = pytest.importorskip("PIL.Image")

    image = Image.new("RGB", (4, 4), "#2a8faf")
    image.putpixel((1, 1), (230, 0, 0))

    _, red_text_image = prepare_ocr_images(image)

    assert red_text_image.getpixel((2, 2)) == 0
    assert red_text_image.getpixel((0, 0)) == 255


def test_merge_cleaned_ocr_lines_keeps_unique_lines_from_ocr_variants():
    lines = merge_cleaned_ocr_lines(
        "Day 12, 16:13: White log line\n",
        "Day 12, 16:13: White log line\nDay 12, 16:14: Your wall was destroyed!\n",
    )

    assert lines == [
        "Day 12, 16:13: White log line",
        "Day 12, 16:14: Your wall was destroyed!",
    ]


def test_new_lines_since_last_scan_dedupes_case_insensitive():
    seen = {"old line"}

    fresh = new_lines_since_last_scan(["Old Line", "New Line"], seen)

    assert fresh == ["New Line"]
    assert "new line" in seen


def test_has_destroyed_structure_alert_matches_screen_tribelog_line():
    lines = ["Day 6529, 18:25:35: Your 'Metal Foundation' was destroyed!"]

    assert has_destroyed_structure_alert(lines) is True


def test_has_destroyed_structure_alert_matches_wrapped_ocr_line():
    lines = ["Day 6529, 18:25:35: Your 'Metal Wall'", "was destroyed!"]

    assert has_destroyed_structure_alert(lines) is True


def test_has_destroyed_structure_alert_ignores_other_destroyed_lines():
    lines = ["Day 6550, 12:10:17: Human demolished a 'Metal Foundation'"]

    assert has_destroyed_structure_alert(lines) is False


def test_resolve_tesseract_cmd_uses_program_files_fallback(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("bot.screen_monitor.shutil.which", lambda _: None)
    monkeypatch.setattr(
        "bot.screen_monitor.os.path.exists",
        lambda path: path == r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    )

    assert resolve_tesseract_cmd() == r"C:\Program Files\Tesseract-OCR\tesseract.exe"
