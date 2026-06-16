"""Loguru-based logging helpers.

We deliberately avoid the stdlib ``logging`` module because Loguru gives us
structured logs, automatic rotation, and clean formatting with zero ceremony.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_INITIALISED = False


def setup_logging(level: str = "INFO", log_dir: str | Path = "logs") -> None:
    """Initialise the global Loguru logger.

    Idempotent: safe to call from multiple entrypoints.
    """
    global _INITIALISED
    if _INITIALISED:
        return

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()  # drop default handler

    # Pretty console handler
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "| <level>{level: <8}</level> "
            "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
            "- <level>{message}</level>"
        ),
        backtrace=True,
        diagnose=False,
    )

    # Rotating file handler
    logger.add(
        log_dir / "market_intel.log",
        level=level.upper(),
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    _INITIALISED = True


def get_logger(name: str | None = None):
    """Return a contextualised logger.

    Loguru uses a single global logger, so we ``bind`` a context name.
    """
    if not _INITIALISED:
        setup_logging()
    return logger.bind(component=name) if name else logger
