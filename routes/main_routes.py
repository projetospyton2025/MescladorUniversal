"""Página inicial."""

from flask import Blueprint, render_template

from config import APP_NAME, PORT

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("index.html", app_name=APP_NAME, port=PORT)
