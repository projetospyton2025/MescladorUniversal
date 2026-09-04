"""Concatenação de arquivos de texto."""

from __future__ import annotations

from pathlib import Path

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _read_text(path: Path) -> str:
    last_error: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise MergeError(
        f"Não foi possível ler o arquivo {path.name} como texto.",
        detail=str(last_error) if last_error else "",
    )


class TextMerger(BaseMerger):
    category = "text"

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        parts: list[str] = []
        for index, path in enumerate(paths):
            percent = 10 + int(70 * (index / len(paths)))
            progress(percent, f"Lendo {path.name}")
            text = _read_text(path)
            parts.append(text if text.endswith("\n") else text + "\n")

        progress(90, "Gravando texto mesclado")
        output.write_text("".join(parts), encoding="utf-8")
        progress(100, "Mesclagem concluída")
        return output
