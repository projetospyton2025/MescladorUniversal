"""Mesclagem de CSV com validação de cabeçalho."""

from __future__ import annotations

import csv
from pathlib import Path

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError


def _open_text(path: Path):
    return path.open("r", encoding="utf-8-sig", newline="")


def _headers(path: Path) -> tuple[list[str], str]:
    with _open_text(path) as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise MergeError(f"O arquivo {path.name} não possui cabeçalho.") from exc
        normalized = [column.strip() for column in header]
        if not any(normalized):
            raise MergeError(f"O arquivo {path.name} possui um cabeçalho vazio.")
        return normalized, delimiter


class CsvMerger(BaseMerger):
    category = "csv"

    def validate_content(self, paths: list[Path]) -> None:
        first_header, _ = _headers(paths[0])
        first_key = [item.casefold() for item in first_header]
        for path in paths[1:]:
            header, _ = _headers(path)
            if [item.casefold() for item in header] != first_key:
                raise MergeError(
                    "Os arquivos CSV possuem colunas incompatíveis. "
                    f"O arquivo {paths[0].name} usa as colunas {', '.join(first_header)} "
                    f"e {path.name} usa {', '.join(header)}."
                )

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        header, delimiter = _headers(paths[0])
        header_key = [item.casefold() for item in header]

        progress(20, "Validando cabeçalhos")
        with output.open("w", encoding="utf-8-sig", newline="") as dest:
            writer = csv.writer(dest, delimiter=delimiter)
            writer.writerow(header)
            for index, path in enumerate(paths):
                percent = 25 + int(65 * (index / len(paths)))
                progress(percent, f"Mesclando {path.name}")
                current_header, current_delimiter = _headers(path)
                if [item.casefold() for item in current_header] != header_key:
                    raise MergeError(
                        f"O arquivo {path.name} possui um cabeçalho diferente dos demais."
                    )
                with _open_text(path) as handle:
                    reader = csv.reader(handle, delimiter=current_delimiter)
                    next(reader, None)
                    for row in reader:
                        if row and any(cell.strip() for cell in row):
                            writer.writerow(row)

        progress(100, "Mesclagem concluída")
        return output
