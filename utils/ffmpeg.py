"""Detecção e execução do FFmpeg/ffprobe."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from config import FFMPEG_PATH, FFPROBE_PATH, MAX_PROCESSING_SECONDS
from services.exceptions import MergeError
from utils.logging_setup import get_logger

logger = get_logger("ffmpeg")

_CREATE_NO_WINDOW = 0
if os.name == "nt":
    _CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _which(configured: str | None, binary: str) -> str | None:
    if configured:
        path = Path(configured)
        if path.exists():
            return str(path)
    found = shutil.which(binary)
    return found


def ffmpeg_cmd() -> str | None:
    return _which(FFMPEG_PATH, "ffmpeg")


def ffprobe_cmd() -> str | None:
    return _which(FFPROBE_PATH, "ffprobe")


def ffmpeg_available() -> bool:
    return ffmpeg_cmd() is not None and ffprobe_cmd() is not None


def require_ffmpeg() -> tuple[str, str]:
    ffmpeg = ffmpeg_cmd()
    ffprobe = ffprobe_cmd()
    if not ffmpeg or not ffprobe:
        raise MergeError(
            "Para mesclar áudio e vídeo é necessário o FFmpeg instalado e disponível no PATH. "
            "Consulte o README para instalar e verificar com o comando ffmpeg -version."
        )
    return ffmpeg, ffprobe


def _startupinfo():
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def run_command(
    args: list[str],
    timeout: int = MAX_PROCESSING_SECONDS,
) -> subprocess.CompletedProcess:
    logger.info("Executando: %s", " ".join(args[:8]) + (" ..." if len(args) > 8 else ""))
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=_startupinfo(),
            creationflags=_CREATE_NO_WINDOW,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise MergeError(
            "O processamento demorou mais do que o tempo máximo permitido. "
            "Tente com arquivos menores.",
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise MergeError(
            "O FFmpeg não foi encontrado. Instale a ferramenta e configure o PATH.",
            detail=str(exc),
        ) from exc
    return completed


def probe(path: Path) -> dict:
    _, ffprobe = require_ffmpeg()
    completed = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=60,
    )
    if completed.returncode != 0:
        raise MergeError(
            f"Não foi possível ler o arquivo {path.name}. "
            "Verifique se o arquivo não está corrompido.",
            detail=completed.stderr,
        )
    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MergeError(
            f"Não foi possível analisar as informações técnicas de {path.name}.",
            detail=str(exc),
        ) from exc


def friendly_ffmpeg_error(stderr: str) -> str:
    text = (stderr or "").lower()
    if "does not match" in text or "incompatible" in text:
        return (
            "Não foi possível mesclar os arquivos porque os parâmetros técnicos são incompatíveis. "
            "O sistema tentará padronizar os arquivos; se o erro persistir, use arquivos "
            "com o mesmo formato."
        )
    if "invalid data" in text or "corrupt" in text:
        return "Um dos arquivos parece estar corrompido ou em um formato inválido."
    if "no such file" in text:
        return "Um dos arquivos não foi encontrado durante o processamento."
    if "permission denied" in text:
        return "O sistema não conseguiu gravar o arquivo de saída. Verifique as permissões da pasta."
    return (
        "Não foi possível mesclar os arquivos de mídia. "
        "Tente utilizar arquivos com o mesmo formato ou permita que o sistema "
        "faça a padronização interna necessária."
    )
