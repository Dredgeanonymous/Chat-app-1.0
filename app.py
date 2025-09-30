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

# ───────────────────────────────────────────────────────────────────────────────
# Paths (robust no matter the working directory)
# ───────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ───────────────────────────────────────────────────────────────────────────────
# App / Socket.IO
# ───────────────────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATES_DIR),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# If you ever scale to multiple instances/workers, add a message queue (e.g. Redis)
# socketio = SocketIO(app, cors_allowed_origins="*", message_queue=os.getenv("REDIS_URL"))
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=70,
)
# Simple moderator code (enter on login)
MOD_CODE = os.environ.get("MOD_CODE", "letmein")

# ───────────────────────────────────────────────────────────────────────────────
# Minimal in-memory state (demo). Persist to DB in production.
# ───────────────────────────────────────────────────────────────────────────────
messages = []          # [{id, user, text, ts}]
online_by_sid = {}     # sid -> {"username": str, "role": "user"|"mod"}
sid_by_username = {}   # username -> sid


def current_user():
    return session.get("username"), session.get("role", "user")


def next_msg_id():
    return f"m{len(messages)+1:06d}"


# ───────────────────────────────────────────────────────────────────────────────
# Context: allow {{ now().year }} in templates
# ───────────────────────────────────────────────────────────────────────────────
@app.context_processor
def inject_now():
    # now() will be callable in templates: now().year
    return {"now": datetime.utcnow}


# ───────────────────────────────────────────────────────────────────────────────
# Top-level pages (all extend base.html)
# ───────────────────────────────────────────────────────────────────────────────
@app.route("/")
def root():
    # Land on login page by default
    return redirect(url_for("landing"))

@app.route("/landing")
def landing():
    return render_template("landing.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/cookies")
def cookies():
    return render_template("cookies.html")


# ───────────────────────────────────────────────────────────────────────────────
# PWA helpers (your base.html uses url_for('manifest') and registers /sw.js)
# Place files at static/manifest.webmanifest and static/sw.js
# ───────────────────────────────────────────────────────────────────────────────
@app.route("/manifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest",
                               mimetype="application/manifest+json")

@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js",
                               mimetype="application/javascript")


# ───────────────────────────────────────────────────────────────────────────────
# Auth-ish (simple demo)
# ───────────────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_code = (request.form.get("mod_code") or "").strip()
        gender   = (request.form.get("gender") or "").strip()  # captured if you want to use it
         avatar = (request.form.get("avatar") or "").strip()

        if not username:
            return render_template("login.html", error="Username is required.")

        role = "mod" if mod_code and mod_code == MOD_CODE else "user"
        session["username"] = username
        session["role"] = role
        session["gender"] = gender
        session["avatar"] = avatar  # may be empty
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


# ───────────────────────────────────────────────────────────────────────────────
# Socket.IO events
# ───────────────────────────────────────────────────────────────────────────────
# Helper to build and broadcast the roster as objects
def broadcast_roster():
    # Turn the dict into a list of {username, role, gender}, sorted by username
    roster = []
    for info in online_by_sid.values():
        roster.append({
            "username": info.get("username"),
            "role": info.get("role", "user"),
            "gender": info.get("gender", ""),
        })
    roster.sort(key=lambda r: (r["username"] or "").lower())
    socketio.emit("online", roster, broadcast=True)
@socketio.on("typing")
def sio_typing(data):
    uname = session.get("username")
    if not uname:
        return
    emit("typing", {"user": uname, "typing": bool((data or {}).get("typing"))}, broadcast=True, include_self=False)

@socketio.on("connect")
def sio_connect(auth):
    sid = request.sid
    username = session.get("username") or f"Anon-{sid[:5]}"
    role = session.get("role", "user")
    gender = session.get("gender", "hidden")

    online_by_sid[sid] = {"username": username, "role": role, "gender": gender}
    sid_by_username[username] = sid

    emit("online", list(online_by_sid.values()), broadcast=True)
@socketio.on("ping_test")
def ping_test():
    emit("pong_test", {"ok": True})

def build_roster():
    roster = [{
        "username": info.get("username"),
        "role": info.get("role", "user"),
        "gender": info.get("gender", "")
    } for info in online_by_sid.values()]
    roster.sort(key=lambda r: (r["username"] or "").lower())
    return roster
@socketio.on("typing")
def sio_typing(data):
    uname = session.get("username")
    if not uname:
        return
    # Notify others only
    emit("typing", {"user": uname, "typing": bool((data or {}).get("typing"))}, broadcast=True, include_self=False)

@socketio.on("roster_request")
def sio_roster_request():
    emit("online", build_roster())

@socketio.on("disconnect")
def sio_disconnect():
    info = online_by_sid.pop(request.sid, None)
    if info:
        uname = info["username"]
        sid_by_username.pop(uname, None)
        broadcast_roster()
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
    # to recipient + echo back to sender
    emit("pm", payload, to=target_sid)
    emit("pm", payload)

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


# ───────────────────────────────────────────────────────────────────────────────
# Dev entrypoint; in production use gunicorn with gevent or gevent-websocket.
# ───────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Local dev:
    #   python app.py
    # Production (Render → Start Command), pick ONE:
    #   gunicorn -k gevent -w 1 app:app
    #   gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
