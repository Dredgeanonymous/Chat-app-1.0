# app.py — Flask + Flask-SocketIO (merged & cleaned)

import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory
)
from flask_socketio import SocketIO, emit, disconnect
from markupsafe import escape

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ── App / Socket.IO (must be before any decorators) ───────────────────────────
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATES_DIR),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=70,
)

# Simple moderator code (enter on login)
MOD_CODE = os.environ.get("MOD_CODE", "letmein")

# ── Minimal in-memory state (demo) ────────────────────────────────────────────
messages = []          # [{id, user, text, ts}]
online_by_sid = {}     # sid -> {"username": str, "role": "user"|"mod", "gender": str}
sid_by_username = {}   # username -> sid

def current_user():
    return session.get("username"), session.get("role", "user")

def next_msg_id():
    return f"m{len(messages)+1:06d}"

# Jinja helper: {{ now().year }}
@app.context_processor
def inject_now():
    return {"now": datetime.utcnow}

# ===================== Routes =====================

@app.route("/")
def root():
    # Land on your landing page by default (you can switch to "login" if you prefer)
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

# ---- PWA files ----
# Serve the manifest at BOTH /manifest.json and /manifest (compat)

@app.route("/manifest")
def manifest():
    # Expect file at: static/manifest.json
    return send_from_directory("static", "manifest.json", mimetype="application/json")

@app.route("/sw.js")
def service_worker():
    # Expect file at: static/sw.js
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/.well-known/assetlinks.json")
def assetlinks():
    # Expect file at: static/.well-known/assetlinks.json
    return send_from_directory("static/.well-known", "assetlinks.json", mimetype="application/json")

# ---- Auth-ish (simple demo) ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_code = (request.form.get("mod_code") or "").strip()
        gender   = (request.form.get("gender") or "").strip()

        if not username:
            return render_template("login.html", error="Username is required.")

        role = "mod" if (mod_code and mod_code == MOD_CODE) else "user"
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

# ================= Socket.IO events =================

# 1) Roster
def broadcast_roster():
    ...
    socketio.emit("online", roster, broadcast=True)
    socketio.emit("online", roster)

# 2) Typing indicator
@socketio.on("typing")
def sio_typing(data):
    uname = session.get("username")
    if not uname:
        return
  emit("typing", {"user": uname, "typing": bool((data or {}).get("typing"))}, broadcast=True, include_self=False)
    socketio.emit(
      "typing",
      {"user": uname, "typing": bool((data or {}).get("typing"))},
      skip_sid=request.sid

# 3) New chat messages
@socketio.on("chat")
def sio_chat(data):
    ...
   emit("chat", msg, broadcast=True)
   socketio.emit("chat", msg)

# 4) Private messages (keep direct send, echo to sender explicitly)
@socketio.on("pm")
def sio_pm(data):
    ...
  emit("pm", payload, to=target_sid)
  emit("pm", payload)
   socketio.emit("pm", payload, to=target_sid)
   socketio.emit("pm", payload, to=request.sid)

# 5) Delete message broadcast
@socketio.on("delete_message")
def sio_delete_message(data):
    ...
   emit("message_deleted", {"id": mid}, broadcast=True)
    socketio.emit("message_deleted", {"id": mid})
@socketio.on("connect")
def sio_connect():
    uname = session.get("username")
    role = session.get("role", "user")
    gender = session.get("gender", "")

    # If they connect without being logged in, drop the socket (keeps room clean)
    if not uname:
        disconnect()
        return

    online_by_sid[request.sid] = {"username": uname, "role": role, "gender": gender}
    sid_by_username[uname] = request.sid

    # Send recent messages to the new client (keep from your previous file)
    emit("chat_history", messages[-100:])

    # Update roster for everyone
    broadcast_roster()

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

# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Dev: python app.py
    # Prod (Render → Start Command): gunicorn -k gevent -w 1 app:app
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
