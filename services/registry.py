"""Catálogo de formatos suportados e detecção de categoria."""

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
        extensions=frozenset({".mp3", ".wav", ".wma", ".m4a", ".aac", ".ogg", ".flac"}),
        output_ext=".mp3",
        needs_ffmpeg=True,
        notes="A extensão de saída segue o primeiro arquivo, quando possível.",
    ),
    FormatSpec(
        category="video",
        category_label="Vídeo",
        extensions=frozenset({".mp4", ".avi", ".mkv", ".mov", ".webm"}),
        output_ext=".mp4",
        needs_ffmpeg=True,
        notes="Diferenças de codec/resolução podem exigir transcodificação interna.",
    ),
    FormatSpec(
        category="image",
        category_label="Imagens",
        extensions=frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}),
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
        category="json",
        category_label="Dados",
        extensions=frozenset({".json"}),
        output_ext=".json",
    ),
    FormatSpec(
        category="csv",
        category_label="Dados",
        extensions=frozenset({".csv"}),
        output_ext=".csv",
    ),
    FormatSpec(
        category="text",
        category_label="Documento",
        extensions=frozenset({".txt"}),
        output_ext=".txt",
    ),
    FormatSpec(
        category="spreadsheet",
        category_label="Planilha",
        extensions=frozenset({".xlsx", ".xls"}),
        output_ext=".xlsx",
        notes="A mesclagem nativa é feita em XLSX. Arquivos XLS devem ser salvos como XLSX.",
    ),
    FormatSpec(
        category="word",
        category_label="Documento",
        extensions=frozenset({".docx", ".doc"}),
        output_ext=".docx",
        notes="A mesclagem nativa é feita em DOCX. Arquivos DOC devem ser salvos como DOCX.",
    ),
)

_EXT_TO_SPEC: dict[str, FormatSpec] = {}
for _spec in FORMATS:
    for _ext in _spec.extensions:
        _EXT_TO_SPEC[_ext] = _spec

ALLOWED_EXTENSIONS = frozenset(_EXT_TO_SPEC)


def extension_of(path: str | Path) -> str:
    return Path(path).suffix.lower()


def spec_for(path: str | Path) -> FormatSpec | None:
    return _EXT_TO_SPEC.get(extension_of(path))


def public_catalog() -> list[dict]:
    """Lista formatos para a interface, sem expor detalhes internos."""
    groups: list[dict] = []
    for spec in FORMATS:
        groups.append(
            {
                "category": spec.category,
                "label": spec.category_label,
                "extensions": sorted(ext.lstrip(".").upper() for ext in spec.extensions),
                "output": spec.output_ext.lstrip(".").upper(),
                "needs_ffmpeg": spec.needs_ffmpeg,
                "notes": spec.notes,
            }
        )
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
