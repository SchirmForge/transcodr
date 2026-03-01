"""Notification service — dispatches alerts to all enabled channels."""

import logging
from typing import TYPE_CHECKING

from src.config.schema import NotificationsConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Orchestrates notifications across all configured channels.

    Channels are initialized once in __init__ based on config.
    Each notify_* method checks the relevant flag before dispatching.
    Channel errors are logged but never re-raised.
    """

    def __init__(self, config: NotificationsConfig) -> None:
        self._config = config
        self._channels: list = []

        if not config.enabled:
            return

        if config.desktop.enabled:
            try:
                from src.notifications.channels.desktop import DesktopChannel
                self._channels.append(DesktopChannel(config.desktop))
                logger.info("Notification channel enabled: desktop")
            except Exception as e:
                logger.error(f"Failed to initialize desktop notification channel: {e}")

        if config.email.enabled:
            try:
                from src.notifications.channels.email import EmailChannel
                self._channels.append(EmailChannel(config.email))
                logger.info("Notification channel enabled: email")
            except Exception as e:
                logger.error(f"Failed to initialize email notification channel: {e}")

        if config.apprise.enabled:
            try:
                from src.notifications.channels.apprise import AppriseChannel
                self._channels.append(AppriseChannel(config.apprise))
                logger.info(f"Notification channel enabled: apprise ({len(config.apprise.urls)} URL(s))")
            except Exception as e:
                logger.error(f"Failed to initialize apprise notification channel: {e}")

    async def _dispatch(self, title: str, body: str) -> None:
        """Send to all enabled channels, swallowing per-channel errors."""
        for channel in self._channels:
            try:
                await channel.send(title, body)
            except Exception as e:
                logger.error(f"Notification channel {type(channel).__name__} failed: {e}")

    async def notify_job_complete(
        self,
        job_id: str,
        profile: str,
        source: str,
        status: str,
        duration_seconds: float | None = None,
        source_size_bytes: int | None = None,
        output_size_bytes: int | None = None,
        error_message: str | None = None,
    ) -> None:
        if not self._config.enabled or not self._config.on_job_complete:
            return
        success = status in ("completed", "warning")
        emoji = "✅" if success else "❌"
        title = f"{emoji} Job {status}: {profile}"
        lines = [f"Source: {source}"]
        if duration_seconds is not None:
            mins, secs = divmod(int(duration_seconds), 60)
            lines.append(f"Duration: {mins}m {secs}s")
        if source_size_bytes and output_size_bytes:
            src_mb = source_size_bytes / 1_048_576
            out_mb = output_size_bytes / 1_048_576
            ratio = output_size_bytes / source_size_bytes * 100
            lines.append(f"Size: {src_mb:.0f} MB → {out_mb:.0f} MB ({ratio:.0f}%)")
        if error_message:
            lines.append(f"Error: {error_message}")
        await self._dispatch(title, "\n".join(lines))

    async def notify_batch_complete(
        self,
        batch_id: str,
        total: int,
        completed: int,
        failed: int,
    ) -> None:
        if not self._config.enabled or not self._config.on_batch_complete:
            return
        emoji = "✅" if failed == 0 else "⚠️"
        title = f"{emoji} Batch complete: {completed}/{total} jobs succeeded"
        lines = [f"Batch: {batch_id[:8]}…"]
        if failed:
            lines.append(f"Failed: {failed}")
        await self._dispatch(title, "\n".join(lines))

    async def notify_queue_empty(self) -> None:
        if not self._config.enabled or not self._config.on_queue_empty:
            return
        await self._dispatch("Queue idle", "All encoding jobs have finished.")

    async def notify_error(self, message: str) -> None:
        if not self._config.enabled or not self._config.on_error:
            return
        await self._dispatch("❗ Transcodr error", message)
