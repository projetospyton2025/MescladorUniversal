"""União de documentos PDF."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError


def _open_pdf(path: Path) -> PdfReader:
    try:
        reader = PdfReader(str(path))
    except PdfReadError as exc:
        raise MergeError(
            f"O arquivo {path.name} não é um PDF válido ou está corrompido.",
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise MergeError(
            f"Não foi possível abrir o PDF {path.name}.",
            detail=str(exc),
        ) from exc
    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception:
            unlocked = False
        if not unlocked:
            raise MergeError(
                f"O arquivo {path.name} está protegido por senha e não pode ser mesclado."
            )
    if len(reader.pages) == 0:
        raise MergeError(f"O arquivo {path.name} não possui páginas.")
    return reader


class PdfMerger(BaseMerger):
    category = "pdf"

    def validate_content(self, paths: list[Path]) -> None:
        for path in paths:
            _open_pdf(path)

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        writer = PdfWriter()
        for index, path in enumerate(paths):
            percent = 10 + int(80 * (index / len(paths)))
            progress(percent, f"Adicionando {path.name}")
            reader = _open_pdf(path)
            writer.append(reader)
        progress(95, "Gravando PDF mesclado")
        with output.open("wb") as handle:
            writer.write(handle)
        progress(100, "Mesclagem concluída")
        return output
