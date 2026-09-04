"""Concatenação de vídeos via FFmpeg, com transcodificação interna se necessário."""

from __future__ import annotations

from pathlib import Path

from services.base import BaseMerger, ProgressCb
from services.exceptions import MergeError
from utils.ffmpeg import friendly_ffmpeg_error, probe, require_ffmpeg, run_command
from utils.logging_setup import get_logger

logger = get_logger("video")


def _stream(info: dict, kind: str) -> dict | None:
    for item in info.get("streams") or []:
        if item.get("codec_type") == kind:
            return item
    return None


def _fps(stream: dict) -> str:
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1"
    if rate in {"0/0", "N/A", None, ""}:
        return "30"
    return rate


def _even(value: int, fallback: int) -> int:
    if value <= 0:
        return fallback
    return value if value % 2 == 0 else value - 1


def _signature(video: dict, audio: dict | None) -> tuple:
    return (
        video.get("codec_name"),
        int(video.get("width") or 0),
        int(video.get("height") or 0),
        video.get("pix_fmt"),
        _fps(video),
        None if audio is None else (
            audio.get("codec_name"),
            audio.get("sample_rate"),
            audio.get("channels"),
        ),
    )


class VideoMerger(BaseMerger):
    category = "video"

    def validate_content(self, paths: list[Path]) -> None:
        require_ffmpeg()
        for path in paths:
            info = probe(path)
            if _stream(info, "video") is None:
                raise MergeError(f"O arquivo {path.name} não contém uma faixa de vídeo válida.")

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        ffmpeg, _ = require_ffmpeg()
        progress(10, "Analisando vídeos")
        probes = [probe(path) for path in paths]
        videos = [_stream(info, "video") for info in probes]
        audios = [_stream(info, "audio") for info in probes]
        if any(item is None for item in videos):
            raise MergeError("Um dos arquivos não contém vídeo válido.")

        list_file = output.parent / f"{output.stem}_list.txt"
        list_file.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\n" for path in paths),
            encoding="utf-8",
        )
        compatible = len({_signature(video, audio) for video, audio in zip(videos, audios)}) == 1
        try:
            if compatible:
                progress(25, "Unindo vídeos sem recodificar")
                if self._concat_copy(ffmpeg, list_file, output):
                    progress(100, "Mesclagem concluída")
                    return output
                logger.info("Concatenação direta de vídeo falhou; padronizando internamente.")

            first = videos[0] or {}
            width = _even(int(first.get("width") or 0), 1280)
            height = _even(int(first.get("height") or 0), 720)
            fps = _fps(first)
            need_audio = any(item is not None for item in audios)
            progress(35, "Padronizando vídeos para mesclagem")
            self._normalize_and_concat(
                ffmpeg, paths, audios, output, width, height, fps, need_audio, progress
            )
            if not output.exists() or output.stat().st_size == 0:
                raise MergeError("O arquivo de vídeo mesclado não foi gerado.")
            progress(100, "Mesclagem concluída")
            return output
        finally:
            list_file.unlink(missing_ok=True)

    def _concat_copy(self, ffmpeg: str, list_file: Path, output: Path) -> bool:
        completed = run_command(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(list_file),
                "-c", "copy", str(output),
            ]
        )
        if completed.returncode == 0 and output.exists() and output.stat().st_size > 0:
            return True
        logger.warning("Falha no concat copy de vídeo: %s", completed.stderr)
        output.unlink(missing_ok=True)
        return False

    def _normalize_and_concat(
        self,
        ffmpeg: str,
        paths: list[Path],
        audios: list[dict | None],
        output: Path,
        width: int,
        height: int,
        fps: str,
        need_audio: bool,
        progress: ProgressCb,
    ) -> None:
        intermediates: list[Path] = []
        list_file = output.parent / f"{output.stem}_norm.txt"
        try:
            for index, path in enumerate(paths):
                percent = 40 + int(40 * (index / len(paths)))
                progress(percent, f"Processando {path.name}")
                mid = output.parent / f"{output.stem}_part_{index}.mp4"
                cmd = [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(path),
                ]
                if need_audio and audios[index] is None:
                    cmd.extend(["-f", "lavfi", "-t", "0.05", "-i", "anullsrc=r=44100:cl=stereo"])
                    # duration is matched via -shortest after mapping video length with apad
                    cmd = [
                        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(path),
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-filter_complex",
                        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v];"
                        f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a]",
                        "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
                        "-shortest",
                        str(mid),
                    ]
                elif need_audio:
                    cmd.extend(
                        [
                            "-vf",
                            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p",
                            "-c:v", "libx264",
                            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                            str(mid),
                        ]
                    )
                else:
                    cmd.extend(
                        [
                            "-vf",
                            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p",
                            "-c:v", "libx264",
                            "-an",
                            str(mid),
                        ]
                    )
                completed = run_command(cmd)
                if completed.returncode != 0:
                    raise MergeError(
                        friendly_ffmpeg_error(completed.stderr),
                        detail=completed.stderr,
                    )
                intermediates.append(mid)

            progress(85, "Unindo vídeos padronizados")
            list_file.write_text(
                "".join(f"file '{item.resolve().as_posix()}'\n" for item in intermediates),
                encoding="utf-8",
            )
            completed = run_command(
                [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(list_file),
                    "-c", "copy",
                    "-movflags", "+faststart",
                    str(output),
                ]
            )
            if completed.returncode != 0:
                raise MergeError(
                    friendly_ffmpeg_error(completed.stderr),
                    detail=completed.stderr,
                )
        finally:
            list_file.unlink(missing_ok=True)
            for item in intermediates:
                item.unlink(missing_ok=True)
