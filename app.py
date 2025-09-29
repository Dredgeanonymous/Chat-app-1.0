# app.py  — Flask + Flask-SocketIO (gevent/gunicorn friendly)

import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session
)
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from markupsafe import escape

# ---------- Paths (robust no matter the working dir) ----------
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ---------- App / Socket.IO ----------
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATES_DIR),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
# If you scale to >1 instance, add a message_queue (e.g., Redis URL)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------- Simple moderator gate ----------
MOD_CODE = os.environ.get("MOD_CODE", "letmein")

# ---------- In-memory state (demo only) ----------
messages = []          # [{id, user, text, ts}]
online_by_sid = {}     # sid -> {"username": str, "role": "user"|"mod"}
sid_by_username = {}   # username -> sid


def current_user():
    uname = session.get("username")
    role = session.get("role", "user")
    return uname, role


def next_msg_id():
    return f"m{len(messages)+1:06d}"


# ---------- Routes ----------
@app.route("/")
def root():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_code = (request.form.get("mod_code") or "").strip()
        # gender is present in the form; capture if you want to store it
        gender = (request.form.get("gender") or "").strip()

        if not username:
            return render_template("login.html", error="Username is required.")

        role = "mod" if mod_code and mod_code == MOD_CODE else "user"
        session["username"] = username
        session["role"] = role
        session["gender"] = gender
        return redirect(url_for("chat"))

    return render_template("login.html", error=None)


@app.route("/chat")
def chat():
    uname, role = current_user()
    if not uname:
        return redirect(url_for("login"))
    return render_template("chat.html", username=uname, role=role)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Socket.IO events ----------
@socketio.on("connect")
def sio_connect():
    uname = session.get("username")
    role = session.get("role", "user")
    if not uname:
        disconnect()
        return

    online_by_sid[request.sid] = {"username": uname, "role": role}
    sid_by_username[uname] = request.sid

    # Send recent history to this client
    emit("chat_history", messages[-100:])

    # Broadcast updated roster (just usernames; JS handles both shapes)
    emit("online", sorted(sid_by_username.keys()), broadcast=True)


@socketio.on("disconnect")
def sio_disconnect():
    info = online_by_sid.pop(request.sid, None)
    if info:
        uname = info["username"]
        sid_by_username.pop(uname, None)
        emit("online", sorted(sid_by_username.keys()), broadcast=True)


@socketio.on("chat")
def sio_chat(data):
    uname = session.get("username")
    if not uname:
        return
    txt = (data or {}).get("text", "").strip()
    if not txt:
        return

    msg = {
        "id": next_msg_id(),
        "user": uname,
        "text": escape(txt),
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    messages.append(msg)
    emit("chat", msg, broadcast=True)


@socketio.on("pm")
def sio_pm(data):
    uname = session.get("username")
    if not uname:
        return

    to_user = (data or {}).get("to", "").strip()
    txt = (data or {}).get("text", "").strip()
    if not to_user or not txt:
        return

    target_sid = sid_by_username.get(to_user)
    if not target_sid:
        return

    payload = {
        "from": uname,
        "to": to_user,
        "text": escape(txt),
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    emit("pm", payload, to=target_sid)
    emit("pm", payload)  # echo to sender


@socketio.on("delete_message")
def sio_delete_message(data):
    role = session.get("role", "user")
    if role != "mod":
        return

    mid = (data or {}).get("id")
    if not mid:
        return

    idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
    if idx is not None:
        messages.pop(idx)
        emit("message_deleted", {"id": mid}, broadcast=True)


# ---------- Entrypoint ----------
if __name__ == "__main__":
    # For local dev only. In Render use gunicorn with gevent or gevent-websocket.
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
