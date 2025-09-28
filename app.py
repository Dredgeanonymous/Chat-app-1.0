import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, emit, disconnect

# ----------------------
# App & SocketIO (no eventlet)
# ----------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
# async_mode='threading' keeps it compatible with Android/PyDroid and Render free tier
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# ----------------------
# Config
# ----------------------
MOD_CODE = os.environ.get("MOD_CODE", "12345")   # change on Render dashboard anytime

# ----------------------
# In-memory state (OK for small demo; use DB/redis for production)
# ----------------------
online_by_sid = {}          # sid -> {"username": str, "role": "user"|"mod"}
messages = []               # simple rolling log in memory

def online_list():
    """Return list of {username, role} currently online."""
    return [{"username": u["username"], "role": u["role"]} for u in online_by_sid.values()]

def broadcast_online():
    """Push new online roster to all clients."""
    socketio.emit("online", online_list())

# ----------------------
# PWA assets
# ----------------------
@app.route("/manifest.webmanifest")
def webmanifest():
    # make sure static/manifest.webmanifest exists
    return send_from_directory("static", "manifest.webmanifest", mimetype="application/manifest+json")

@app.route("/sw.js")
def service_worker():
    # make sure static/sw.js exists
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

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
        mod_code = (request.form.get("mod_code") or "").strip()
        if not username:
            return render_template("login.html", error="Please enter a username.")
        role = "mod" if (mod_code and mod_code == MOD_CODE) else "user"
        session["username"] = username
        session["role"] = role
        return redirect(url_for("chat"))
    return render_template("login.html")

@app.route("/chat", methods=["GET"])
def chat():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html", username=session["username"], role=session.get("role", "user"))

@app.route("/logout")
def logout():
    # socket will also disconnect; front-end typically reconnects after page change
    session.clear()
    return redirect(url_for("login"))

# ----------------------
# Socket.IO events
# ----------------------
@socketio.on("connect")
def handle_connect():
    # Only allow if logged-in via Flask session
    username = session.get("username")
    role = session.get("role", "user")
    if not username:
        # reject connection if no login
        return False
    # register online
    online_by_sid[request.sid] = {"username": username, "role": role}
    # send recent messages just to the new client
    emit("history", messages)
    # update everyone with online roster
    broadcast_online()

@socketio.on("disconnect")
def handle_disconnect():
    if request.sid in online_by_sid:
        online_by_sid.pop(request.sid, None)
        broadcast_online()

@socketio.on("send_message")
def on_send_message(data):
    """
    data: {"text": "..."} from the client
    """
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
        "ts": datetime.now(timezone.utc).isoformat()
    }
    messages.append(entry)
    # Broadcast to all clients (no 'broadcast' kwarg; new python-socketio API broadcasts by default)
    socketio.emit("new_message", entry)

@socketio.on("mod_action")
def on_mod_action(data):
    """
    Simple example of a moderator action:
    data: {"action": "delete", "message_id": 12}
    """
    if session.get("role") != "mod":
        # silently ignore non-mods
        return
    action = (data or {}).get("action")
    if action == "delete":
        mid = (data or {}).get("message_id")
        # remove message
        idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
        if idx is not None:
            removed = messages.pop(idx)
            socketio.emit("message_deleted", {"id": removed["id"]})
    # you can extend here: mute user, clear chat, pin message, etc.

# ----------------------
# Run
# ----------------------
if __name__ == "__main__":
    # On PyDroid run like a normal script:
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))