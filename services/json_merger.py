"""Mesclagem de arquivos JSON com preservação do conteúdo original."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError

_UPLOAD_PREFIX = re.compile(r"^\d{3}_")


def _load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MergeError(
            f"O arquivo {path.name} não está em UTF-8. Salve o JSON com encoding UTF-8 e tente novamente.",
            detail=str(exc),
        ) from exc
    if not text.strip():
        raise MergeError(f"O arquivo {path.name} está vazio.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MergeError(
            f"O arquivo {path.name} não contém um JSON válido (linha {exc.lineno}, coluna {exc.colno}).",
            detail=str(exc),
        ) from exc


def _type_name(value: Any) -> str:
    if isinstance(value, dict):
        return "objeto"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "nulo"
    return type(value).__name__


def _source_label(path: Path) -> str:
    """Nome original do arquivo, sem o prefixo 000_ gravado no upload."""
    name = path.name
    if _UPLOAD_PREFIX.match(name):
        return name[4:] or name
    return name


def _unique_labels(paths: list[Path]) -> list[str]:
    labels: list[str] = []
    used: dict[str, int] = {}
    for path in paths:
        base = _source_label(path)
        count = used.get(base.lower(), 0)
        used[base.lower()] = count + 1
        if count == 0:
            labels.append(base)
            continue
        stem = Path(base).stem
        suffix = Path(base).suffix
        labels.append(f"{stem}_{count}{suffix}")
    return labels


def _bundle_by_source(paths: list[Path], payloads: list[Any]) -> dict[str, Any]:
    """Agrupa cada JSON intacto sob o nome do arquivo de origem."""
    return {
        label: payload
        for label, payload in zip(_unique_labels(paths), payloads, strict=True)
    }


def _merge_objects(left: dict, right: dict, trail: str) -> dict:
    merged = dict(left)
    for key, right_value in right.items():
        location = f"{trail}.{key}" if trail else key
        if key not in merged:
            merged[key] = right_value
            continue
        left_value = merged[key]
        if isinstance(left_value, dict) and isinstance(right_value, dict):
            merged[key] = _merge_objects(left_value, right_value, location)
        elif isinstance(left_value, list) and isinstance(right_value, list):
            merged[key] = left_value + right_value
        elif left_value == right_value:
            continue
        else:
            raise MergeError(
                "Os JSONs possuem estruturas incompatíveis. "
                f"A chave \"{location}\" aparece com valores diferentes "
                f"({_type_name(left_value)} e {_type_name(right_value)}) "
                "e não pode ser combinada automaticamente."
            )
    return merged


class JsonMerger(BaseMerger):
    category = "json"

    def validate_content(self, paths: list[Path]) -> None:
        for path in paths:
            _load_json(path)

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        progress(15, f"Lendo {paths[0].name}")
        payloads = []
        for index, path in enumerate(paths):
            percent = 15 + int(50 * (index / len(paths)))
            progress(percent, f"Lendo {path.name}")
            payloads.append(_load_json(path))

        kinds = {_type_name(item) for item in payloads}
        if kinds == {"array"}:
            progress(70, "Concatenando arrays JSON")
            result: Any = []
            for item in payloads:
                result.extend(item)
        elif kinds == {"objeto"}:
            progress(70, "Mesclando objetos JSON")
            result = {}
            for item in payloads:
                result = _merge_objects(result, item, "")
        else:
            progress(70, "Agrupando JSONs com estruturas diferentes")
            result = _bundle_by_source(paths, payloads)

        progress(90, "Gravando JSON mesclado")
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        progress(100, "Mesclagem concluída")
        return output
