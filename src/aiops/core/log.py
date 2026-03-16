"""Structured logging setup with rich handler."""

from __future__ import annotations

import logging
import sys

from rich.logging import RichHandler

_CONFIGURED = False


def _setup_root(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        force=True,
    )
    _CONFIGURED = True


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """Get a named logger with rich formatting."""
    _setup_root(level or "INFO")
    logger = logging.getLogger(name)
    if level:
        logger.setLevel(level)
    return logger
