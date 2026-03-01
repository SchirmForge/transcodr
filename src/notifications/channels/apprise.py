"""Apprise notification channel (ntfy, Gotify, Pushover, and 80+ services)."""

import logging

from src.config.schema import AppriseNotificationConfig

logger = logging.getLogger(__name__)

try:
    import apprise as _apprise_lib
    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False


class AppriseChannel:
    """Send notifications via Apprise (supports ntfy, Gotify, Pushover, etc.)."""

    def __init__(self, config: AppriseNotificationConfig) -> None:
        if not APPRISE_AVAILABLE:
            raise RuntimeError(
                "The 'apprise' package is not installed. "
                "Run: pip install apprise"
            )
        self._ap = _apprise_lib.Apprise()
        for url in config.urls:
            self._ap.add(url)
        logger.debug(f"Apprise channel initialized with {len(config.urls)} URL(s)")

    async def send(self, title: str, body: str) -> None:
        try:
            await self._ap.async_notify(title=title, body=body)
        except Exception as e:
            logger.warning(f"Apprise notification failed: {e}")
