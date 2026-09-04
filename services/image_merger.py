"""Une imagens (e PDFs mistos) em um único PDF."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError
from services.registry import extension_of, extensions_for

_IMAGE_EXTS = extensions_for("image")


def _open_image(path: Path) -> Image.Image:
    try:
        image = Image.open(path)
        image.load()
        return image
    except UnidentifiedImageError as exc:
        raise MergeError(
            f"O arquivo {path.name} não é uma imagem válida.",
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise MergeError(
            f"Não foi possível abrir a imagem {path.name}.",
            detail=str(exc),
        ) from exc


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGB", "L"}:
        return image.convert("RGB")
    if image.mode in {"RGBA", "LA", "P"}:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _frames(image: Image.Image) -> list[Image.Image]:
    frames = [_to_rgb(image.copy())]
    n_frames = getattr(image, "n_frames", 1)
    for index in range(1, n_frames):
        image.seek(index)
        frames.append(_to_rgb(image.copy()))
    image.seek(0)
    return frames


def _image_to_pdf_bytes(path: Path) -> bytes:
    with _open_image(path) as image:
        frames = _frames(image)
    buffer = BytesIO()
    first, rest = frames[0], frames[1:]
    first.save(buffer, format="PDF", resolution=100.0, save_all=bool(rest), append_images=rest)
    for frame in frames:
        frame.close()
    return buffer.getvalue()


class ImageMerger(BaseMerger):
    category = "image"

    def validate_content(self, paths: list[Path]) -> None:
        for path in paths:
            ext = extension_of(path)
            if ext == ".pdf":
                reader = PdfReader(str(path))
                if reader.is_encrypted:
                    raise MergeError(f"O PDF {path.name} está protegido por senha.")
                continue
            if ext not in _IMAGE_EXTS:
                raise MergeError(f"O arquivo {path.name} não é uma imagem suportada.")
            _open_image(path).close()

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        writer = PdfWriter()
        for index, path in enumerate(paths):
            percent = 10 + int(80 * (index / len(paths)))
            progress(percent, f"Processando {path.name}")
            ext = extension_of(path)
            if ext == ".pdf":
                writer.append(PdfReader(str(path)))
                continue
            pdf_bytes = _image_to_pdf_bytes(path)
            writer.append(PdfReader(BytesIO(pdf_bytes)))

        progress(95, "Gravando PDF de imagens")
        with output.open("wb") as handle:
            writer.write(handle)
        progress(100, "Mesclagem concluída")
        return output
