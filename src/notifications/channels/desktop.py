"""Desktop notification channel via notify-send (libnotify)."""

import asyncio
import logging

from src.config.schema import DesktopNotificationConfig

logger = logging.getLogger(__name__)


class DesktopChannel:
    """Send notifications via notify-send."""

    def __init__(self, config: DesktopNotificationConfig) -> None:
        self._config = config

    async def send(self, title: str, body: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "notify-send",
                "-a", "Transcodr",
                "--icon", "video-x-generic",
                title,
                body,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except FileNotFoundError:
            logger.warning("notify-send not found — install libnotify-bin for desktop notifications")
        except Exception as e:
            logger.warning(f"Desktop notification failed: {e}")
