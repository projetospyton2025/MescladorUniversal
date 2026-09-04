"""Configuração de logs em arquivo e console."""

from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config import LOG_FOLDER, LOG_LEVEL


def setup_logging() -> logging.Logger:
    LOG_FOLDER.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("mesclador")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_path = LOG_FOLDER / f"mesclador_{datetime.now():%Y-%m-%d}.log"
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console)
    logger.propagate = False
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    base = logging.getLogger("mesclador")
    if name:
        return base.getChild(name)
    return base
