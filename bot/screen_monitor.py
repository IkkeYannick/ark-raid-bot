import asyncio
import io
import logging
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger("RaidBot.screen_monitor")


@dataclass(frozen=True)
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


def parse_region(value: str | None) -> ScreenRegion | None:
    if not value:
        return None

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("SCREEN_LOG_REGION must be x,y,width,height")

    x, y, width, height = [int(part) for part in parts]
    if width <= 0 or height <= 0:
        raise ValueError("SCREEN_LOG_REGION width and height must be positive")

    return ScreenRegion(x=x, y=y, width=width, height=height)


def default_tribelog_region(screen_width: int, screen_height: int) -> ScreenRegion:
    width = int(screen_width * 0.22)
    height = int(screen_height * 0.62)
    x = int((screen_width - width) / 2)
    y = int(screen_height * 0.19)
    return ScreenRegion(x=x, y=y, width=width, height=height)


def clean_ocr_text(text: str) -> list[str]:
    cleaned_lines = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        line = re.sub(r"\s+", " ", line)
        line = line.replace("|", "I")

        if len(line) < 5:
            continue

        cleaned_lines.append(line)

    return cleaned_lines


def prepare_ocr_images(image):
    from PIL import Image, ImageChops, ImageOps

    rgb_image = image.convert("RGB")

    grayscale_image = ImageOps.grayscale(rgb_image)
    grayscale_image = ImageOps.autocontrast(grayscale_image)
    grayscale_image = grayscale_image.resize(
        (grayscale_image.width * 2, grayscale_image.height * 2),
    )

    red, green, blue = rgb_image.split()
    red_signal = ImageChops.lighter(
        ImageChops.subtract(red, green),
        ImageChops.subtract(red, blue),
    )
    red_signal = ImageOps.autocontrast(red_signal)
    red_text_image = red_signal.point(lambda pixel: 0 if pixel >= 35 else 255)
    nearest_filter = getattr(getattr(Image, "Resampling", Image), "NEAREST")
    red_text_image = red_text_image.resize(
        (red_text_image.width * 2, red_text_image.height * 2),
        resample=nearest_filter,
    )

    return [grayscale_image, red_text_image]


def merge_cleaned_ocr_lines(*texts: str) -> list[str]:
    merged_lines = []
    seen = set()

    for text in texts:
        for line in clean_ocr_text(text):
            key = line.casefold()
            if key in seen:
                continue

            merged_lines.append(line)
            seen.add(key)

    return merged_lines


def screenshot_to_png_bytes(image) -> io.BytesIO:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def new_lines_since_last_scan(lines: Iterable[str], seen: set[str]) -> list[str]:
    fresh = []

    for line in lines:
        key = line.casefold()
        if key in seen:
            continue

        fresh.append(line)
        seen.add(key)

    return fresh


def has_destroyed_structure_alert(lines: Iterable[str]) -> bool:
    text = " ".join(lines)
    return bool(
        re.search(
            r"\byour\s+[`'\"‘’]?[^`'\"‘’]+[`'\"‘’]?\s+was\s+destroyed\b",
            text,
            re.IGNORECASE,
        )
    )


def resolve_tesseract_cmd() -> str | None:
    configured_cmd = os.getenv("TESSERACT_CMD")
    if configured_cmd:
        return configured_cmd

    path_cmd = shutil.which("tesseract")
    if path_cmd:
        return path_cmd

    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.exists(candidate):
            return candidate

    return None


class OverlayWindow:
    def __init__(self, region: ScreenRegion):
        self.region = region
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="TribelogOverlay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        try:
            import tkinter as tk
        except Exception as exc:
            logger.warning("Could not start screen monitor overlay: %s", exc)
            return

        try:
            root = tk.Tk()
            root.title("ARK Tribelog Monitor")
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.55)
            root.protocol("WM_DELETE_WINDOW", lambda: None)

            transparent = "magenta"
            root.configure(bg=transparent)
            try:
                root.attributes("-transparentcolor", transparent)
            except tk.TclError:
                pass

            root.geometry(f"{self.region.width}x{self.region.height}+{self.region.x}+{self.region.y}")

            canvas = tk.Canvas(
                root,
                width=self.region.width,
                height=self.region.height,
                highlightthickness=0,
                bg=transparent,
            )
            canvas.pack(fill="both", expand=True)
            canvas.create_rectangle(
                3,
                3,
                self.region.width - 3,
                self.region.height - 3,
                outline="#00f0ff",
                width=4,
            )
            canvas.create_text(
                12,
                12,
                anchor="nw",
                fill="#00f0ff",
                font=("Segoe UI", 11, "bold"),
                text="TRIBELOG OCR",
            )

            def keep_visible() -> None:
                if self._stop_event.is_set():
                    root.destroy()
                    return

                root.attributes("-topmost", True)
                root.lift()
                root.after(1000, keep_visible)

            root.after(100, keep_visible)
            root.mainloop()
        except Exception as exc:
            logger.warning("Screen monitor overlay stopped unexpectedly: %s", exc)


class ScreenTribeLogMonitor:
    def __init__(
        self,
        channel,
        region: ScreenRegion | None = None,
        interval_seconds: float = 3.0,
        show_overlay: bool = True,
        role_mention: str | None = None,
    ):
        self.channel = channel
        self.region = region
        self.interval_seconds = interval_seconds
        self.show_overlay = show_overlay
        self.role_mention = role_mention
        self._task: asyncio.Task | None = None
        self._seen_lines: set[str] = set()
        self._overlay: OverlayWindow | None = None
        self._sent_error_notice = False

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            logger.debug("Screen tribelog monitor start requested, but it is already running.")
            return

        logger.debug("Starting screen tribelog monitor task.")
        self._task = asyncio.create_task(self._run(), name="screen-tribelog-monitor")

    async def stop(self) -> None:
        logger.debug("Stopping screen tribelog monitor task.")
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._overlay:
            self._overlay.stop()

        self._task = None
        logger.debug("Screen tribelog monitor task stopped.")

    async def _run(self) -> None:
        logger.debug(
            "Screen monitor logger active. effective_level=%s root_effective_level=%s",
            logger.getEffectiveLevel(),
            logging.getLogger().getEffectiveLevel(),
        )

        try:
            import pytesseract
            from PIL import ImageGrab
        except Exception as exc:
            await self.channel.send(
                "Screen tribelog monitor could not start. Install `pillow pytesseract` "
                "and make sure the Tesseract OCR app is installed."
            )
            logger.exception("Screen monitor dependencies are missing: %s", exc)
            return

        tesseract_cmd = resolve_tesseract_cmd()
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            logger.debug("Using Tesseract command: %s", tesseract_cmd)
        else:
            logger.debug("Using Tesseract command from PATH.")

        if self.region is None:
            logger.debug("No screen region configured. Capturing full screen once to detect size.")
            screen_width, screen_height = ImageGrab.grab().size
            self.region = default_tribelog_region(screen_width, screen_height)
            logger.debug(
                "Auto-selected screen tribelog region: x=%s y=%s width=%s height=%s",
                self.region.x,
                self.region.y,
                self.region.width,
                self.region.height,
            )

        self._ensure_overlay()

        await self.channel.send(
            "Screen tribelog monitor started. Watching "
            f"`x={self.region.x}, y={self.region.y}, w={self.region.width}, h={self.region.height}`."
        )
        logger.debug(
            "Screen tribelog monitor running. interval=%ss overlay=%s region=(%s,%s,%s,%s)",
            self.interval_seconds,
            self.show_overlay,
            self.region.x,
            self.region.y,
            self.region.width,
            self.region.height,
        )

        while True:
            try:
                self._ensure_overlay()
                logger.debug(
                    "Recapturing screen tribelog region: x=%s y=%s width=%s height=%s bbox=%s",
                    self.region.x,
                    self.region.y,
                    self.region.width,
                    self.region.height,
                    self.region.bbox,
                )
                screenshot = await asyncio.to_thread(ImageGrab.grab, bbox=self.region.bbox)
                logger.debug("Screen capture complete. image_size=%s mode=%s", screenshot.size, screenshot.mode)

                ocr_images = await asyncio.to_thread(prepare_ocr_images, screenshot)
                logger.debug(
                    "OCR image preprocessing complete. image_count=%s image_size=%s modes=%s",
                    len(ocr_images),
                    ocr_images[0].size if ocr_images else None,
                    [ocr_image.mode for ocr_image in ocr_images],
                )

                logger.debug("Sending captured region variants to Tesseract OCR.")
                texts = []
                for index, ocr_image in enumerate(ocr_images):
                    text = await asyncio.to_thread(
                        pytesseract.image_to_string,
                        ocr_image,
                        config="--psm 6",
                    )
                    texts.append(text)
                    logger.debug("Raw OCR output preview variant=%s: %r", index, text[:500])

                cleaned_lines = merge_cleaned_ocr_lines(*texts)
                fresh_lines = new_lines_since_last_scan(cleaned_lines, self._seen_lines)
                logger.debug(
                    "Screen tribelog OCR scan complete. raw_chars=%s cleaned_lines=%s fresh_lines=%s seen_lines=%s",
                    sum(len(text) for text in texts),
                    len(cleaned_lines),
                    len(fresh_lines),
                    len(self._seen_lines),
                )
                if fresh_lines:
                    await self._send_lines(fresh_lines)
                else:
                    logger.debug("No new OCR lines to send this scan.")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Screen tribelog OCR scan failed.")
                await self._send_error_once()

            await asyncio.sleep(self.interval_seconds)

    def _ensure_overlay(self) -> None:
        if not self.show_overlay or self.region is None:
            return

        if self._overlay and self._overlay.is_running:
            return

        self._overlay = OverlayWindow(self.region)
        self._overlay.start()
        logger.debug("Screen tribelog overlay started.")

    async def _send_lines(self, lines: list[str]) -> None:
        logger.debug("Sending %s OCR line(s) to Discord channel %s.", len(lines), self.channel.id)
        now = int(time.time())
        message = "\n".join(lines)

        if len(message) > 1800:
            message = message[:1800] + "\n..."

        prefix = ""
        if self.role_mention and has_destroyed_structure_alert(lines):
            prefix = f"{self.role_mention} "

        await self.channel.send(f"{prefix}**Screen tribelog OCR** <t:{now}:T>\n```text\n{message}\n```")
        logger.debug("OCR lines sent to Discord.")

    async def _send_error_once(self) -> None:
        if getattr(self, "_sent_error_notice", False):
            return

        self._sent_error_notice = True
        await self.channel.send("Screen tribelog OCR hit an error. Check the bot console logs.")


class ScreenTribeLogScreenshotMonitor:
    def __init__(
        self,
        channel,
        region: ScreenRegion | None = None,
        interval_seconds: float = 30.0,
        show_overlay: bool = True,
    ):
        self.channel = channel
        self.region = region
        self.interval_seconds = interval_seconds
        self.show_overlay = show_overlay
        self._task: asyncio.Task | None = None
        self._overlay: OverlayWindow | None = None
        self._sent_error_notice = False

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            logger.debug("Screen tribelog screenshot monitor start requested, but it is already running.")
            return

        logger.debug("Starting screen tribelog screenshot monitor task.")
        self._task = asyncio.create_task(self._run(), name="screen-tribelog-screenshot-monitor")

    async def stop(self) -> None:
        logger.debug("Stopping screen tribelog screenshot monitor task.")
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._overlay:
            self._overlay.stop()

        self._task = None
        logger.debug("Screen tribelog screenshot monitor task stopped.")

    async def _run(self) -> None:
        try:
            import discord
            from PIL import ImageGrab
        except Exception as exc:
            await self.channel.send(
                "Screen tribelog screenshot monitor could not start. Install `pillow` "
                "and make sure `discord.py` is installed."
            )
            logger.exception("Screen screenshot monitor dependencies are missing: %s", exc)
            return

        if self.region is None:
            logger.debug("No screen region configured. Capturing full screen once to detect size.")
            screen_width, screen_height = ImageGrab.grab().size
            self.region = default_tribelog_region(screen_width, screen_height)
            logger.debug(
                "Auto-selected screen tribelog screenshot region: x=%s y=%s width=%s height=%s",
                self.region.x,
                self.region.y,
                self.region.width,
                self.region.height,
            )

        self._ensure_overlay()

        await self.channel.send(
            "Screen tribelog screenshot monitor started. Posting screenshots from "
            f"`x={self.region.x}, y={self.region.y}, w={self.region.width}, h={self.region.height}`."
        )
        logger.debug(
            "Screen tribelog screenshot monitor running. interval=%ss overlay=%s region=(%s,%s,%s,%s)",
            self.interval_seconds,
            self.show_overlay,
            self.region.x,
            self.region.y,
            self.region.width,
            self.region.height,
        )

        while True:
            try:
                self._ensure_overlay()
                logger.debug(
                    "Capturing screen tribelog screenshot: x=%s y=%s width=%s height=%s bbox=%s",
                    self.region.x,
                    self.region.y,
                    self.region.width,
                    self.region.height,
                    self.region.bbox,
                )
                screenshot = await asyncio.to_thread(ImageGrab.grab, bbox=self.region.bbox)
                image_buffer = await asyncio.to_thread(screenshot_to_png_bytes, screenshot)
                now = int(time.time())
                await self.channel.send(
                    f"**Screen tribelog screenshot** <t:{now}:T>",
                    file=discord.File(image_buffer, filename="tribelog.png"),
                )
                logger.debug("Screen tribelog screenshot sent to Discord.")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Screen tribelog screenshot capture failed.")
                await self._send_error_once()

            await asyncio.sleep(self.interval_seconds)

    def _ensure_overlay(self) -> None:
        if not self.show_overlay or self.region is None:
            return

        if self._overlay and self._overlay.is_running:
            return

        self._overlay = OverlayWindow(self.region)
        self._overlay.start()
        logger.debug("Screen tribelog screenshot overlay started.")

    async def _send_error_once(self) -> None:
        if self._sent_error_notice:
            return

        self._sent_error_notice = True
        await self.channel.send("Screen tribelog screenshot monitor hit an error. Check the bot console logs.")
