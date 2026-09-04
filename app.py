"""Ponto de entrada do Mesclador Universal."""

from __future__ import annotations

from flask import Flask

from config import HOST, MAX_TOTAL_SIZE, PORT
from routes.main_routes import main_bp
from routes.merge_routes import merge_bp
from utils.cleanup import start_cleanup_thread
from utils.file_utils import ensure_directories
from utils.logging_setup import setup_logging


def create_app() -> Flask:
    setup_logging()
    ensure_directories()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_TOTAL_SIZE

    @app.errorhandler(413)
    def too_large(_error):
        return {
            "ok": False,
            "error": "O conjunto de arquivos excede o limite de envio. Reduza o tamanho e tente novamente.",
        }, 413

    app.register_blueprint(main_bp)
    app.register_blueprint(merge_bp)
    start_cleanup_thread()
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
