"""Limpeza periódica de uploads, temporários, saídas e jobs expirados."""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

from config import (
    CLEANUP_INTERVAL_SECONDS,
    JOB_TTL_SECONDS,
    OUTPUT_FOLDER,
    OUTPUT_TTL_SECONDS,
    TEMP_FOLDER,
    UPLOAD_FOLDER,
)
from utils.logging_setup import get_logger

logger = get_logger("cleanup")
_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _is_older_than(path: Path, max_age: int) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age > max_age


def _remove_path(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Falha ao remover %s: %s", path, exc)


def cleanup_job_inputs(job_id: str) -> None:
    for root in (UPLOAD_FOLDER, TEMP_FOLDER):
        _remove_path(root / job_id)


def cleanup_expired() -> None:
    now_folders = (
        (UPLOAD_FOLDER, JOB_TTL_SECONDS),
        (TEMP_FOLDER, JOB_TTL_SECONDS),
        (OUTPUT_FOLDER, OUTPUT_TTL_SECONDS),
    )
    for folder, ttl in now_folders:
        if not folder.exists():
            continue
        for item in folder.iterdir():
            if item.name.startswith("."):
                continue
            if _is_older_than(item, ttl):
                logger.info("Removendo arquivo expirado: %s", item.name)
                _remove_path(item)


def _loop() -> None:
    logger.info("Limpeza automática iniciada (intervalo %ss).", CLEANUP_INTERVAL_SECONDS)
    while not _stop_event.wait(CLEANUP_INTERVAL_SECONDS):
        try:
            cleanup_expired()
        except Exception:
            logger.exception("Erro inesperado na limpeza de arquivos temporários.")


def start_cleanup_thread() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="cleanup", daemon=True)
    _thread.start()
