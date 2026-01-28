"""Logging configuration for video transcoding."""

import json
import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs log records as JSON for easier parsing and analysis.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        return json.dumps(log_data)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable formatter for CLI output.

    Includes color coding for different log levels (if terminal supports it).
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, *args, use_colors: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            reset = self.RESET
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    structured: bool = False,
    console: bool = True,
) -> None:
    """
    Setup logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (if None, no file logging)
        structured: Use JSON structured logging for files
        console: Enable console logging
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (human-readable)
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_formatter = HumanReadableFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            use_colors=True,
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler (structured or human-readable)
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "videotranscode.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file

        if structured:
            file_formatter = StructuredFormatter()
        else:
            file_formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    root_logger.info(f"Logging initialized (level={level})")


class JobLogger:
    """
    Context manager for per-job logging.

    Creates a separate log file for each job, making it easier
    to debug specific encoding operations.
    """

    def __init__(self, job_id: str, log_dir: Path):
        """
        Initialize job logger.

        Args:
            job_id: Unique job identifier
            log_dir: Directory for log files
        """
        self.job_id = job_id
        self.log_dir = log_dir
        self.log_file = log_dir / f"job-{job_id}.log"
        self.logger = logging.getLogger(f"job.{job_id}")
        self.handler: Optional[logging.Handler] = None

    def __enter__(self):
        """Setup job-specific logging."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.handler = logging.FileHandler(self.log_file)
        self.handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.handler.setFormatter(formatter)

        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)

        self.logger.info(f"Job {self.job_id} started")

        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup job logging."""
        if exc_type:
            self.logger.error(
                f"Job {self.job_id} failed with exception: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb),
            )
        else:
            self.logger.info(f"Job {self.job_id} completed")

        if self.handler:
            self.logger.removeHandler(self.handler)
            self.handler.close()

    def get_log_path(self) -> Path:
        """Get path to job log file."""
        return self.log_file


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
