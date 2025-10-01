# app.py — Flask + Flask-SocketIO (clean + roster_request)

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

# ── App / Socket.IO (define before any decorators) ────────────────────────────
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

MOD_CODE = os.environ.get("MOD_CODE", "letmein")

# ── In-memory state (demo) ────────────────────────────────────────────────────
messages = []          # [{id, user, text, ts, avatar?}]
online_by_sid = {}     # sid -> {"username","role","gender","avatar"}
sid_by_username = {}   # username -> sid

def next_msg_id() -> str:
    return f"m{len(messages)+1:06d}"

# Jinja helper: {{ now().year }}
@app.context_processor
def inject_now():
    return {"now": datetime.utcnow}

# ───────────────────────────────── Routes ─────────────────────────────────────

@app.route("/")
def root():
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

# ---- PWA files (match base.html calls url_for('manifest') and url_for('sw')) --
@app.route("/manifest.json")
@app.route("/manifest")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/json")

@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/.well-known/assetlinks.json")
def assetlinks():
    return send_from_directory("static/.well-known", "assetlinks.json", mimetype="application/json")

# ---- Auth / Chat -------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_code = (request.form.get("mod_code") or "").strip()
        gender   = (request.form.get("gender") or "").strip()
        avatar   = (request.form.get("avatar") or "").strip()

        if not username:
            return render_template("login.html", error="Username is required.")

        role = "mod" if (mod_code and mod_code == MOD_CODE) else "user"
        session["username"] = username
        session["role"] = role
        session["gender"] = gender
        session["avatar"] = avatar
        return redirect(url_for("chat"))

    return render_template("login.html", error=None)

@app.route("/chat")
def chat():
    uname = session.get("username")
    if not uname:
        return redirect(url_for("login"))
    return render_template("chat.html", username=uname, role=session.get("role", "user"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ───────────────────────────── Socket.IO events ───────────────────────────────

def build_roster():
    roster = [{
        "username": info.get("username"),
        "role": info.get("role", "user"),
        "gender": info.get("gender", ""),
        "avatar": info.get("avatar", ""),
    } for info in online_by_sid.values()]
    roster.sort(key=lambda r: (r["username"] or "").lower())
    return roster

def broadcast_roster():
    socketio.emit("online", build_roster())

@socketio.on("connect")
def sio_connect():
    # Require a logged-in session for sockets
    uname = session.get("username")
    if not uname:
        disconnect()
        return

    online_by_sid[request.sid] = {
        "username": uname,
        "role": session.get("role", "user"),
        "gender": session.get("gender", ""),
        "avatar": session.get("avatar", ""),
    }
    sid_by_username[uname] = request.sid

    # send recent chat history to the new client (trim to last 100)
    emit("chat_history", messages[-100:])
    broadcast_roster()

@socketio.on("disconnect")
def sio_disconnect():
    info = online_by_sid.pop(request.sid, None)
    if info:
        sid_by_username.pop(info.get("username"), None)
        broadcast_roster()

@socketio.on("roster_request")
def sio_roster_request():
    # Client calls this right after (re)connect to fill the Online list
    emit("online", build_roster())

@socketio.on("typing")
def sio_typing(data):
    uname = session.get("username")
    if not uname:
        return
    emit("typing",
         {"user": uname, "typing": bool((data or {}).get("typing"))},
         broadcast=True, include_self=False)

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
        "avatar": session.get("avatar", ""),
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
        "avatar": session.get("avatar", ""),
    }
    emit("pm", payload, to=target_sid)  # to recipient
    emit("pm", payload)                 # echo back to sender

@socketio.on("delete_message")
def sio_delete_message(data):
    if session.get("role", "user") != "mod":
        return
    mid = (data or {}).get("id")
    if not mid:
        return
    for i, m in enumerate(messages):
        if m["id"] == mid:
            messages.pop(i)
            emit("message_deleted", {"id": mid}, broadcast=True)
            break

# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Dev: python app.py
    # Prod (Render start command): gunicorn -k gevent -w 1 app:app
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
