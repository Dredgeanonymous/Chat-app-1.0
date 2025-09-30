# app.py — Flask + Flask-SocketIO (gevent/gunicorn friendly)

import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory
)
from flask_socketio import SocketIO, emit, disconnect
from markupsafe import escape

# ───────── Paths (robust regardless of working dir)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ───────── App / Socket.IO
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATES_DIR),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# If you scale to >1 instance, add a message queue (e.g., Redis
