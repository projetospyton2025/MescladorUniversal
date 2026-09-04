"""Mesclagem de documentos Word DOCX."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError
from services.registry import extension_of


def _open_docx(path: Path) -> Document:
    if extension_of(path) != ".docx":
        raise MergeError(
            "Arquivos DOC não podem ser mesclados diretamente. Salve como DOCX e tente novamente."
        )
    try:
        return Document(str(path))
    except Exception as exc:
        raise MergeError(
            f"O arquivo {path.name} não é um documento Word válido.",
            detail=str(exc),
        ) from exc


def _append_document(target: Document, source: Document) -> None:
    target.add_page_break()
    source_body = source.element.body
    target_body = target.element.body
    sect_pr = target_body.find(qn("w:sectPr"))
    if sect_pr is not None:
        target_body.remove(sect_pr)
    for child in list(source_body):
        if child.tag == qn("w:sectPr"):
            continue
        target_body.append(deepcopy(child))
    if sect_pr is not None:
        target_body.append(sect_pr)


class DocMerger(BaseMerger):
    category = "word"

    def validate_content(self, paths: list[Path]) -> None:
        for path in paths:
            _open_docx(path)

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        progress(15, f"Lendo {paths[0].name}")
        merged = _open_docx(paths[0])
        for index, path in enumerate(paths[1:], start=1):
            percent = 20 + int(70 * (index / max(len(paths) - 1, 1)))
            progress(percent, f"Adicionando {path.name}")
            _append_document(merged, _open_docx(path))
        progress(95, "Gravando documento mesclado")
        merged.save(str(output))
        progress(100, "Mesclagem concluída")
        return output
