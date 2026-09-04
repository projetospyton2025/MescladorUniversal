"""Catálogo de formatos suportados e detecção de categoria.

As extensões ficam agrupadas por família (áudio, vídeo, imagens, documentos,
planilhas, dados e apresentações). A chave `category` identifica o processador;
`category_label` é o nome exibido. CSV e XLSX compartilham o rótulo Planilha,
mas permanecem em processadores distintos para não misturar os fluxos.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.exceptions import MergeError

INCOMPATIBLE_MESSAGE = (
    "Os arquivos selecionados possuem formatos incompatíveis. "
    "Selecione arquivos compatíveis para realizar a mesclagem."
)


@dataclass(frozen=True)
class FormatSpec:
    category: str
    category_label: str
    extensions: frozenset[str]
    output_ext: str
    needs_ffmpeg: bool = False
    notes: str = ""


FORMATS: tuple[FormatSpec, ...] = (
    FormatSpec(
        category="audio",
        category_label="Áudio",
        extensions=frozenset({".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav", ".wma"}),
        output_ext=".mp3",
        needs_ffmpeg=True,
        notes="A extensão de saída segue o primeiro arquivo, quando possível.",
    ),
    FormatSpec(
        category="video",
        category_label="Vídeo",
        extensions=frozenset({".avi", ".mkv", ".mov", ".mp4", ".webm"}),
        output_ext=".mp4",
        needs_ffmpeg=True,
        notes="Diferenças de codec/resolução podem exigir transcodificação interna.",
    ),
    FormatSpec(
        category="image",
        category_label="Imagens",
        extensions=frozenset({".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}),
        output_ext=".pdf",
        notes="Imagens são unidas em um único PDF.",
    ),
    FormatSpec(
        category="pdf",
        category_label="Documento",
        extensions=frozenset({".pdf"}),
        output_ext=".pdf",
    ),
    FormatSpec(
        category="text",
        category_label="Documento",
        extensions=frozenset({".txt"}),
        output_ext=".txt",
    ),
    FormatSpec(
        category="word",
        category_label="Documento",
        extensions=frozenset({".doc", ".docx"}),
        output_ext=".docx",
        notes="A mesclagem nativa é feita em DOCX. Arquivos DOC devem ser salvos como DOCX.",
    ),
    FormatSpec(
        category="csv",
        category_label="Planilha",
        extensions=frozenset({".csv"}),
        output_ext=".csv",
    ),
    FormatSpec(
        category="spreadsheet",
        category_label="Planilha",
        extensions=frozenset({".xls", ".xlsx"}),
        output_ext=".xlsx",
        notes="A mesclagem nativa é feita em XLSX. Arquivos XLS devem ser salvos como XLSX.",
    ),
    FormatSpec(
        category="json",
        category_label="Dados",
        extensions=frozenset({".json"}),
        output_ext=".json",
        notes=(
            "Arrays são concatenados e objetos são mesclados. "
            "Raízes diferentes ficam agrupadas pelo nome do arquivo, sem alterar o conteúdo."
        ),
    ),
    FormatSpec(
        category="presentation",
        category_label="Apresentações",
        extensions=frozenset({".ppt", ".pptx"}),
        output_ext=".pptx",
        notes="A mesclagem nativa é feita em PPTX. Arquivos PPT devem ser salvos como PPTX.",
    ),
)

_EXT_TO_SPEC: dict[str, FormatSpec] = {}
for _spec in FORMATS:
    for _ext in _spec.extensions:
        key = _ext.lower()
        if not key.startswith("."):
            key = f".{key}"
        if key in _EXT_TO_SPEC:
            raise RuntimeError(f"Extensão duplicada no catálogo: {key}")
        _EXT_TO_SPEC[key] = _spec

ALLOWED_EXTENSIONS = frozenset(_EXT_TO_SPEC)


def extension_of(path: str | Path) -> str:
    return Path(path).suffix.lower()


def spec_for(path: str | Path) -> FormatSpec | None:
    return _EXT_TO_SPEC.get(extension_of(path))


def extensions_for(category: str) -> frozenset[str]:
    spec = next((item for item in FORMATS if item.category == category), None)
    return spec.extensions if spec else frozenset()


def public_catalog() -> list[dict]:
    """Lista formatos para a interface, agrupados pela família visível."""
    groups: list[dict] = []
    index: dict[str, dict] = {}
    for spec in FORMATS:
        key = spec.category_label
        if key not in index:
            item = {
                "category": spec.category,
                "label": spec.category_label,
                "extensions": set(),
                "output": spec.output_ext.lstrip(".").upper(),
                "needs_ffmpeg": spec.needs_ffmpeg,
                "notes": spec.notes,
            }
            index[key] = item
            groups.append(item)
        else:
            item = index[key]
            item["needs_ffmpeg"] = bool(item["needs_ffmpeg"] or spec.needs_ffmpeg)
            if spec.notes and spec.notes not in item["notes"]:
                item["notes"] = f"{item['notes']} {spec.notes}".strip()
        item["extensions"].update(ext.lstrip(".").upper() for ext in spec.extensions)
    for item in groups:
        item["extensions"] = sorted(item["extensions"])
    return groups


def detect_from_names(names: list[str]) -> dict:
    """Identifica categoria/formato a partir dos nomes dos arquivos."""
    if len(names) < 2:
        raise MergeError("Selecione pelo menos dois arquivos para mesclar.")

    specs: list[FormatSpec] = []
    unknown: list[str] = []
    for name in names:
        spec = spec_for(name)
        if spec is None:
            unknown.append(Path(name).name)
        else:
            specs.append(spec)

    if unknown:
        listed = ", ".join(unknown[:5])
        raise MergeError(
            f"O formato de alguns arquivos não é suportado: {listed}. "
            "Selecione arquivos compatíveis para realizar a mesclagem."
        )

    categories = {spec.category for spec in specs}
    if categories <= {"image", "pdf"}:
        category = "pdf" if categories == {"pdf"} else "image"
        spec = next(item for item in FORMATS if item.category == category)
        extensions = sorted({extension_of(name).lstrip(".").upper() for name in names})
        format_label = extensions[0] if len(extensions) == 1 else " + ".join(extensions)
        return {
            "category": spec.category,
            "category_label": "Documento" if category == "pdf" else "Imagens",
            "format_label": format_label,
            "output_ext": ".pdf",
            "needs_ffmpeg": False,
            "mixed_extensions": len(extensions) > 1,
        }

    if len(categories) != 1:
        raise MergeError(INCOMPATIBLE_MESSAGE)

    spec = specs[0]
    extensions = sorted({extension_of(name).lstrip(".").upper() for name in names})
    if spec.category == "spreadsheet" and any(extension_of(name) == ".xls" for name in names):
        raise MergeError(
            "Arquivos XLS (Excel 97-2003) não podem ser mesclados diretamente. "
            "Abra o arquivo no Excel ou no LibreOffice e salve como XLSX."
        )
    if spec.category == "word" and any(extension_of(name) == ".doc" for name in names):
        raise MergeError(
            "Arquivos DOC (Word 97-2003) não podem ser mesclados diretamente. "
            "Abra o documento no Word ou no LibreOffice e salve como DOCX."
        )
    if spec.category == "presentation" and any(extension_of(name) == ".ppt" for name in names):
        raise MergeError(
            "Arquivos PPT (PowerPoint 97-2003) não podem ser mesclados diretamente. "
            "Abra a apresentação no PowerPoint ou no LibreOffice e salve como PPTX."
        )

    output_ext = extension_of(names[0])
    if spec.category in {"image"}:
        output_ext = spec.output_ext
    format_label = extensions[0] if len(extensions) == 1 else " + ".join(extensions)
    return {
        "category": spec.category,
        "category_label": spec.category_label,
        "format_label": format_label,
        "output_ext": output_ext,
        "needs_ffmpeg": spec.needs_ffmpeg,
        "mixed_extensions": len(extensions) > 1,
    }
