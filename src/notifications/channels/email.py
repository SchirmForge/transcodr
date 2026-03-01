"""Email notification channel via SMTP (stdlib smtplib)."""

import asyncio
import logging
import os
import smtplib
from email.mime.text import MIMEText

from src.config.schema import EmailNotificationConfig

logger = logging.getLogger(__name__)


class EmailChannel:
    """Send notifications via SMTP email."""

    def __init__(self, config: EmailNotificationConfig) -> None:
        self._config = config

    async def send(self, title: str, body: str) -> None:
        if not self._config.recipients:
            logger.warning("Email notification skipped: no recipients configured")
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._send_sync, title, body)
        except Exception as e:
            logger.warning(f"Email notification failed: {e}")

    def _send_sync(self, title: str, body: str) -> None:
        password = self._config.smtp_password or os.environ.get("TRANSCODR_SMTP_PASSWORD", "")
        msg = MIMEText(body)
        msg["Subject"] = f"[Transcodr] {title}"
        msg["From"] = self._config.from_address
        msg["To"] = ", ".join(self._config.recipients)
        with smtplib.SMTP(self._config.smtp_server, self._config.smtp_port) as smtp:
            if self._config.use_tls:
                smtp.starttls()
            if self._config.smtp_user:
                smtp.login(self._config.smtp_user, password)
            smtp.sendmail(
                self._config.from_address,
                self._config.recipients,
                msg.as_string(),
            )
        logger.debug(f"Email sent to {self._config.recipients}: {title}")
