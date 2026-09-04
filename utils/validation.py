"""Validação de quantidade, tamanho, extensão e compatibilidade."""

from __future__ import annotations

from pathlib import Path

from config import MAX_FILE_SIZE, MAX_FILES, MAX_TOTAL_SIZE, MIN_FILES
from services.exceptions import MergeError
from services.registry import ALLOWED_EXTENSIONS, detect_from_names, extension_of
from utils.file_utils import format_size, original_name


def validate_count(count: int) -> None:
    if count < MIN_FILES:
        raise MergeError("Selecione pelo menos dois arquivos para mesclar.")
    if count > MAX_FILES:
        raise MergeError(
            f"É possível mesclar no máximo {MAX_FILES} arquivos por vez. "
            "Reduza a seleção e tente novamente."
        )


def validate_size(size: int, filename: str) -> None:
    if size <= 0:
        raise MergeError(f"O arquivo {original_name(filename)} está vazio.")
    if size > MAX_FILE_SIZE:
        raise MergeError(
            f"O arquivo {original_name(filename)} excede o limite de "
            f"{format_size(MAX_FILE_SIZE)} por arquivo."
        )


def validate_total_size(total: int) -> None:
    if total > MAX_TOTAL_SIZE:
        raise MergeError(
            f"O conjunto selecionado excede o limite total de {format_size(MAX_TOTAL_SIZE)}."
        )


def validate_extension(filename: str) -> None:
    ext = extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise MergeError(
            f"A extensão {ext or '(sem extensão)'} não é suportada. "
            "Selecione arquivos compatíveis para realizar a mesclagem."
        )


def validate_upload_batch(files: list) -> dict:
    """Valida a lista de FileStorage do Flask antes de gravar no disco."""
    validate_count(len(files))
    names: list[str] = []
    total = 0
    for item in files:
        filename = original_name(item.filename or "")
        if not filename:
            raise MergeError("Um dos arquivos enviados está sem nome.")
        validate_extension(filename)
        item.stream.seek(0, 2)
        size = item.stream.tell()
        item.stream.seek(0)
        validate_size(size, filename)
        total += size
        names.append(filename)
    validate_total_size(total)
    return detect_from_names(names)


def validate_existing_files(paths: list[Path]) -> dict:
    validate_count(len(paths))
    names: list[str] = []
    total = 0
    for path in paths:
        if not path.is_file():
            raise MergeError(f"O arquivo {path.name} não foi encontrado.")
        size = path.stat().st_size
        validate_size(size, path.name)
        validate_extension(path.name)
        total += size
        names.append(path.name)
    validate_total_size(total)
    return detect_from_names(names)
