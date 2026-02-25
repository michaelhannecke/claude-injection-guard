"""Structured logger for the injection guard."""

import logging
import sys
from pathlib import Path


def setup_logger(config: dict = None) -> logging.Logger:
    config = config or {}
    level_str = config.get("level", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    fmt = config.get("format", "%(asctime)s [%(levelname)s] injection-guard: %(message)s")

    logger = logging.getLogger("injection-guard")
    logger.setLevel(level)
    logger.handlers.clear()

    # Always log to stderr (Claude Code reads stdout for hook responses)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)

    # Optional file handler
    log_file = config.get("file")
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(file_handler)

    return logger
