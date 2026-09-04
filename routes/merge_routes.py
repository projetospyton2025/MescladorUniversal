"""Rotas de mesclagem, progresso e download."""

from __future__ import annotations

import threading
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from config import (
    APP_NAME,
    MAX_FILE_SIZE,
    MAX_FILES,
    MAX_TOTAL_SIZE,
    MIN_FILES,
    PORT,
)
from services.exceptions import MergeError
from services.merge_service import detect_selection, jobs, result_file, run_merge_job
from services.registry import public_catalog
from utils.ffmpeg import ffmpeg_available
from utils.file_utils import job_upload_dir, original_name, safe_filename
from utils.logging_setup import get_logger
from utils.validation import validate_upload_batch

merge_bp = Blueprint("merge", __name__)
logger = get_logger("routes")


@merge_bp.get("/api/config")
def api_config():
    return jsonify(
        {
            "app_name": APP_NAME,
            "port": PORT,
            "min_files": MIN_FILES,
            "max_files": MAX_FILES,
            "max_file_size": MAX_FILE_SIZE,
            "max_total_size": MAX_TOTAL_SIZE,
            "ffmpeg": ffmpeg_available(),
            "formats": public_catalog(),
        }
    )


@merge_bp.post("/api/detect")
def api_detect():
    payload = request.get_json(silent=True) or {}
    names = payload.get("names") or []
    try:
        detected = detect_selection([str(name) for name in names])
        return jsonify({"ok": True, "detected": detected})
    except MergeError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), 400


@merge_bp.post("/api/merge")
def api_merge():
    files = request.files.getlist("files")
    output_name = (request.form.get("output_name") or "").strip()
    try:
        if not files:
            raise MergeError("Nenhum arquivo foi enviado.")
        detected = validate_upload_batch(files)
        job = jobs.create()
        upload_dir = job_upload_dir(job.id)
        saved: list[Path] = []
        used_names: set[str] = set()
        for index, item in enumerate(files):
            filename = safe_filename(original_name(item.filename or f"arquivo_{index + 1}"))
            candidate = filename
            suffix = 1
            while candidate.lower() in used_names:
                stem = Path(filename).stem
                ext = Path(filename).suffix
                candidate = f"{stem}_{suffix}{ext}"
                suffix += 1
            used_names.add(candidate.lower())
            path = upload_dir / f"{index:03d}_{candidate}"
            item.save(path)
            saved.append(path)

        logger.info("Upload recebido job=%s arquivos=%s tipo=%s", job.id, [p.name for p in saved], detected)
        thread = threading.Thread(
            target=run_merge_job,
            args=(job.id, saved, output_name),
            name=f"merge-{job.id[:8]}",
            daemon=True,
        )
        thread.start()
        return jsonify({"ok": True, "job_id": job.id, "detected": detected}), 202
    except MergeError as exc:
        logger.warning("Upload rejeitado: %s", exc.user_message)
        return jsonify({"ok": False, "error": exc.user_message}), 400
    except Exception:
        logger.exception("Falha inesperada no upload")
        return jsonify(
            {
                "ok": False,
                "error": "Não foi possível receber os arquivos. Tente novamente.",
            }
        ), 500


@merge_bp.get("/api/jobs/<job_id>")
def api_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "Operação não encontrada ou expirada."}), 404
    return jsonify({"ok": True, "job": job.to_dict()})


@merge_bp.get("/api/download/<job_id>")
def api_download(job_id: str):
    job = jobs.get(job_id)
    if job is None or job.status != "done":
        return jsonify({"ok": False, "error": "O arquivo ainda não está pronto para download."}), 404
    try:
        path = result_file(job)
        download_name = job.result_name or path.name
        return send_file(path, as_attachment=True, download_name=download_name)
    except MergeError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), 404
