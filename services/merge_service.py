"""Orquestração da mesclagem: detecção, validação, dispatch e jobs."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from config import DEFAULT_OUTPUT_STEM, JOB_TTL_SECONDS, OUTPUT_FOLDER
from services.audio_merger import AudioMerger
from services.csv_merger import CsvMerger
from services.doc_merger import DocMerger
from services.excel_merger import ExcelMerger
from services.exceptions import MergeError
from services.image_merger import ImageMerger
from services.json_merger import JsonMerger
from services.pdf_merger import PdfMerger
from services.registry import detect_from_names
from services.text_merger import TextMerger
from services.video_merger import VideoMerger
from utils.cleanup import cleanup_job_inputs
from utils.file_utils import format_size, output_path_for, unique_job_id
from utils.logging_setup import get_logger
from utils.validation import validate_existing_files

logger = get_logger("merge")

MERGERS = {
    "audio": AudioMerger(),
    "video": VideoMerger(),
    "image": ImageMerger(),
    "pdf": PdfMerger(),
    "json": JsonMerger(),
    "csv": CsvMerger(),
    "text": TextMerger(),
    "spreadsheet": ExcelMerger(),
    "word": DocMerger(),
}


@dataclass
class Job:
    id: str
    status: str = "queued"
    progress: int = 0
    message: str = "Na fila"
    error: str | None = None
    result_name: str | None = None
    result_path: str | None = None
    result_size: int | None = None
    category_label: str | None = None
    format_label: str | None = None
    created_at: float = field(default_factory=time.time)
    elapsed_ms: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "result_name": self.result_name,
            "result_size": self.result_size,
            "result_size_label": format_size(self.result_size or 0) if self.result_size else None,
            "category_label": self.category_label,
            "format_label": self.format_label,
            "elapsed_ms": self.elapsed_ms,
        }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job = Job(id=unique_job_id())
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def purge_expired(self) -> None:
        now = time.time()
        with self._lock:
            stale = [job_id for job_id, job in self._jobs.items() if now - job.created_at > JOB_TTL_SECONDS]
            for job_id in stale:
                self._jobs.pop(job_id, None)


jobs = JobStore()


def _progress_updater(job: Job) -> Callable[[int, str], None]:
    def update(percent: int, message: str) -> None:
        job.progress = max(0, min(100, int(percent)))
        job.message = message
        logger.info("Job %s | %s%% | %s", job.id, job.progress, message)

    return update


def run_merge_job(
    job_id: str,
    paths: list[Path],
    output_name: str | None,
) -> None:
    job = jobs.get(job_id)
    if job is None:
        return
    started = time.perf_counter()
    names = [path.name for path in paths]
    logger.info("Início da operação %s | arquivos=%s", job_id, names)
    try:
        job.status = "processing"
        job.message = "Validando arquivos"
        job.progress = 5
        detected = validate_existing_files(paths)
        job.category_label = detected["category_label"]
        job.format_label = detected["format_label"]
        logger.info(
            "Job %s | tipo=%s | formato=%s",
            job_id,
            detected["category_label"],
            detected["format_label"],
        )

        merger = MERGERS[detected["category"]]
        merger.validate_content(paths)

        stem = (output_name or "").strip() or DEFAULT_OUTPUT_STEM
        target = output_path_for(job_id, stem, detected["output_ext"])
        progress = _progress_updater(job)
        progress(12, "Iniciando mesclagem")
        merger.merge(paths, target, progress)

        size = target.stat().st_size
        job.result_path = str(target)
        job.result_name = (
            target.name[len(job_id) + 1 :]
            if target.name.startswith(f"{job_id}_")
            else target.name
        )
        job.result_size = size
        job.status = "done"
        job.progress = 100
        job.message = "Mesclagem concluída"
        job.elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Conclusão %s | arquivo=%s | tamanho=%s | %sms",
            job_id,
            target.name,
            format_size(size),
            job.elapsed_ms,
        )
    except MergeError as exc:
        logger.error("Erro de mesclagem %s: %s | detalhe=%s", job_id, exc.user_message, exc.detail)
        job.status = "error"
        job.error = exc.user_message
        job.message = exc.user_message
    except Exception:
        logger.exception("Erro inesperado na mesclagem %s", job_id)
        job.status = "error"
        job.error = (
            "Não foi possível concluir a mesclagem. "
            "Verifique os arquivos e tente novamente."
        )
        job.message = job.error
    finally:
        cleanup_job_inputs(job_id)


def detect_selection(names: list[str]) -> dict:
    return detect_from_names(names)


def result_file(job: Job) -> Path:
    if not job.result_path:
        raise MergeError("O arquivo de resultado ainda não está disponível.")
    path = Path(job.result_path).resolve()
    root = OUTPUT_FOLDER.resolve()
    if root not in path.parents and path.parent != root:
        raise MergeError("Caminho de download inválido.")
    if not path.is_file():
        raise MergeError("O arquivo mesclado expirou ou foi removido. Execute a mesclagem novamente.")
    return path
