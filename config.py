"""Configurações centralizadas do Mesclador Universal."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_NAME = "Mesclador Universal"
HOST = "127.0.0.1"
PORT = 5111

UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"
TEMP_FOLDER = BASE_DIR / "temp"
LOG_FOLDER = BASE_DIR / "logs"

MIN_FILES = 2
MAX_FILES = 40
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB por arquivo
MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB no total

OUTPUT_TTL_SECONDS = 60 * 60  # 1 hora
JOB_TTL_SECONDS = 60 * 60
CLEANUP_INTERVAL_SECONDS = 15 * 60
MAX_PROCESSING_SECONDS = 3 * 60 * 60

# None = detectar automaticamente no PATH
FFMPEG_PATH = None
FFPROBE_PATH = None

DEFAULT_OUTPUT_STEM = "arquivo_mesclado"
LOG_LEVEL = "INFO"
