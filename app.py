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
socketio = SocketIO(app, cors_allowed_origins="*")  # no async_mode here
# ----------------------
# Config
# ----------------------
MOD_CODE = os.environ.get("MOD_CODE", "12345")

# ----------------------
# In-memory state (demo only)
# ----------------------
online_by_sid = {}     # sid -> {"username": str, "role": "user"|"mod"}
messages = []          # list of dicts

def online_list():
    return [{"username": v["username"], "role": v["role"]} for v in online_by_sid.values()]

def broadcast_online():
    socketio.emit("online", online_list())

# ----------------------
# Optional PWA files
# ----------------------
@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest", mimetype="application/manifest+json")

@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

# ----------------------
# API (used by chat.js to fetch roster once on load)
# ----------------------
@app.route("/api/online")
def api_online():
    return jsonify(online_list())

# ----------------------
# Pages
# ----------------------
@app.route("/", methods=["GET"])
def root():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_try  = (request.form.get("mod_code") or "").strip()
        if not username:
            return render_template("login.html", error="Please enter a username.")
        session["username"] = username
        session["role"] = "mod" if (mod_try and mod_try == MOD_CODE) else "user"
        return redirect(url_for("chat"))
    return render_template("login.html")

@app.route("/chat")
def chat():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template(
        "chat.html",
        username=session["username"],
        role=session.get("role", "user"),
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ----------------------
# Socket.IO events
# ----------------------
@socketio.on("connect")
def sio_connect():
    # Require logged-in session
    username = session.get("username")
    role = session.get("role", "user")
    if not username:
        return False  # reject

    # Track online
    online_by_sid[request.sid] = {"username": username, "role": role}

    # Send backlog only to this client (the names match your chat.js)
    emit("chat_history", messages)

    # Update everyone’s online list
    broadcast_online()

@socketio.on("disconnect")
def sio_disconnect():
    if online_by_sid.pop(request.sid, None) is not None:
        broadcast_online()

@socketio.on("send_message")
def sio_send_message(data):
    if "username" not in session:
        disconnect()
        return
    text = (data or {}).get("text", "").strip()
    if not text:
        return
    entry = {
        "id": len(messages) + 1,
        "username": session["username"],
        "role": session.get("role", "user"),
        "text": text,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    messages.append(entry)
    # name matches chat.js listener
    socketio.emit("new_message", entry)

@socketio.on("delete_message")
def sio_delete_message(data):
    # moderator-only
    if session.get("role") != "mod":
        return
    mid = (data or {}).get("id")
    if not mid:
        return
    idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
    if idx is None:
        return
    removed = messages.pop(idx)
    socketio.emit("message_deleted", {"id": removed["id"]})

# ----------------------
# Entrypoint
# ----------------------
if __name__ == "__main__":
    # For local runs. On Render we use Gunicorn via Procfile.
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
