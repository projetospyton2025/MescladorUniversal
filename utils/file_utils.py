"""Operações seguras de arquivo."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from config import OUTPUT_FOLDER, TEMP_FOLDER, UPLOAD_FOLDER
from services.exceptions import MergeError

_UNSAFE_CHARS = re.compile(r'[<>:"|?*\\/ \x00-\x1f]+')


def ensure_directories() -> None:
    for folder in (UPLOAD_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER):
        folder.mkdir(parents=True, exist_ok=True)


def original_name(filename: str) -> str:
    return Path(filename.replace("\\", "/")).name


def safe_filename(filename: str, fallback: str = "arquivo") -> str:
    """Remove caminhos e caracteres perigosos, preservando acentos."""
    name = original_name(filename).strip().strip(".")
    name = _UNSAFE_CHARS.sub("_", name)
    name = re.sub(r"_+", "_", name).strip("._")
    if not name:
        name = fallback
    stem = Path(name).stem[:120]
    suffix = Path(name).suffix[:12]
    cleaned = f"{stem}{suffix}" if suffix else stem
    return cleaned or fallback


def unique_job_id() -> str:
    return uuid.uuid4().hex


def job_upload_dir(job_id: str) -> Path:
    path = UPLOAD_FOLDER / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def job_temp_dir(job_id: str) -> Path:
    path = TEMP_FOLDER / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def output_path_for(job_id: str, filename: str, expected_ext: str) -> Path:
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    name = safe_filename(filename, fallback="arquivo_mesclado")
    stem = Path(name).stem or "arquivo_mesclado"
    ext = expected_ext if expected_ext.startswith(".") else f".{expected_ext}"
    if Path(name).suffix.lower() != ext.lower():
        name = f"{stem}{ext}"
    return OUTPUT_FOLDER / f"{job_id}_{name}"


def validate_stored_path(path: Path, allowed_root: Path) -> Path:
    resolved = path.resolve()
    root = allowed_root.resolve()
    if root not in resolved.parents and resolved != root:
        raise MergeError("Caminho de arquivo inválido.")
    return resolved


def format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"
