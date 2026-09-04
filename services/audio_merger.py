"""Concatenação de arquivos de áudio via FFmpeg."""

from __future__ import annotations

from pathlib import Path

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError
from utils.ffmpeg import concat_duration_ok, friendly_ffmpeg_error, probe, require_ffmpeg, run_command
from utils.logging_setup import get_logger

logger = get_logger("audio")

_AUDIO_CODECS = {
    ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    ".wav": ["-c:a", "pcm_s16le"],
    ".flac": ["-c:a", "flac"],
    ".ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    ".m4a": ["-c:a", "aac", "-b:a", "192k"],
    ".aac": ["-c:a", "aac", "-b:a", "192k"],
    ".wma": ["-c:a", "wmav2", "-b:a", "192k"],
}


def _audio_stream(info: dict) -> dict | None:
    for stream in info.get("streams") or []:
        if stream.get("codec_type") == "audio":
            return stream
    return None


def _signature(stream: dict) -> tuple:
    return (
        stream.get("codec_name"),
        stream.get("sample_rate"),
        stream.get("channels"),
        stream.get("sample_fmt"),
    )


class AudioMerger(BaseMerger):
    category = "audio"

    def validate_content(self, paths: list[Path]) -> None:
        require_ffmpeg()
        for path in paths:
            info = probe(path)
            if _audio_stream(info) is None:
                raise MergeError(
                    f"O arquivo {path.name} não contém uma faixa de áudio válida."
                )

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        ffmpeg, _ = require_ffmpeg()
        progress(12, "Analisando faixas de áudio")
        signatures = []
        for path in paths:
            stream = _audio_stream(probe(path))
            if stream is None:
                raise MergeError(f"O arquivo {path.name} não contém áudio válido.")
            signatures.append(_signature(stream))

        list_file = output.parent / f"{output.stem}_list.txt"
        list_file.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\n" for path in paths),
            encoding="utf-8",
        )

        same_params = len(set(signatures)) == 1
        try:
            if same_params:
                progress(30, "Unindo áudios sem recodificar")
                copied = self._concat_copy(ffmpeg, list_file, output)
                if copied and concat_duration_ok(paths, output):
                    progress(100, "Mesclagem concluída")
                    return output
                logger.info("Concatenação direta falhou; padronizando áudio.")
                output.unlink(missing_ok=True)

            progress(40, "Padronizando e concatenando áudio")
            self._concat_transcode(ffmpeg, list_file, output)
            if not output.exists() or output.stat().st_size == 0:
                raise MergeError("O arquivo de áudio mesclado não foi gerado.")
            progress(100, "Mesclagem concluída")
            return output
        finally:
            list_file.unlink(missing_ok=True)

    def _concat_copy(self, ffmpeg: str, list_file: Path, output: Path) -> bool:
        completed = run_command(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(output),
            ]
        )
        if completed.returncode == 0 and output.exists() and output.stat().st_size > 0:
            return True
        logger.warning("Falha no concat copy de áudio: %s", completed.stderr)
        output.unlink(missing_ok=True)
        return False

    def _concat_transcode(self, ffmpeg: str, list_file: Path, output: Path) -> None:
        codec_args = _AUDIO_CODECS.get(output.suffix.lower(), ["-c:a", "libmp3lame", "-q:a", "2"])
        completed = run_command(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-vn",
                *codec_args,
                str(output),
            ]
        )
        if completed.returncode != 0:
            raise MergeError(
                friendly_ffmpeg_error(completed.stderr),
                detail=completed.stderr,
            )
