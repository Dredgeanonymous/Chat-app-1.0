import os
from datetime import datetime, timezone
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory, jsonify
)
from flask_socketio import SocketIO, emit, disconnect

# ----------------------
# Flask + Socket.IO
# ----------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")

# cookies play nice on https
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
)

# WebSockets are available on the paid Render plan.
# We keep async_mode="threading" (works fine on Render)
# and let the server upgrade to WebSocket automatically.
socketio = SocketIO(app, async
