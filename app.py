import os
from datetime import datetime
from flask import send_from_directory import (
    Flask, render_template, request, redirect,
    url_for, session
)
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from markupsafe import escape

# ---------- Config ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple moderator gate (change this!)
MOD_CODE = os.environ.get("MOD_CODE", "letmein")

# ---------- In-memory state (demo only) ----------
messages = []  # [{id, user, text, ts}]
online_by_sid = {}  # sid -> {"username": str, "role": "user"|"mod"}
sid_by_username = {}  # username -> sid

def current_user():
    uname = session.get("username")
    role = session.get("role", "user")
    return uname, role

def next_msg_id():
    return f"m{len(messages)+1:06d}"

# ---------- Routes ----------
@app.route("/")
def root():
    # Send users to login first
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_code = (request.form.get("mod_code") or "").strip()

        if not username:
            return render_template("login.html", error="Username is required.")

        role = "mod" if mod_code and mod_code == MOD_CODE else "user"
        session["username"] = username
        session["role"] = role
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
    @app.route("/manifest")
def manifest():
    # Make sure this file exists at: static/manifest.webmanifest
    return send_from_directory("static", "manifest.webmanifest",
                               mimetype="application/manifest+json")

@app.route("/sw")
def sw():
    # Make sure this file exists at: static/sw.js
    return send_from_directory("static", "sw.js",
                               mimetype="application/javascript")

# ---------- Socket.IO events ----------
@socketio.on("connect")
def sio_connect():
    uname = session.get("username")
    role = session.get("role", "user")
    if not uname:
        # Not logged in -> refuse socket
        disconnect()
        return

    online_by_sid[request.sid] = {"username": uname, "role": role}
    sid_by_username[uname] = request.sid

    # Send initial state to this client
    emit("chat_history", messages[-100:])  # last 100 msgs

    # Broadcast updated online list
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
    """Public chat message"""
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
    """Private message: {to: username, text: str}"""
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
    # send to target & echo back to sender
    emit("pm", payload, to=target_sid)
    emit("pm", payload)

@socketio.on("delete_message")
def sio_delete_message(data):
    """Moderator-only delete by id: {id: 'm000001'}"""
    role = session.get("role", "user")
    if role != "mod":
        return

    mid = (data or {}).get("id")
    if not mid:
        return

    # remove the message if it exists
    idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
    if idx is not None:
        messages.pop(idx)
        emit("message_deleted", {"id": mid}, broadcast=True)

# ---------- Run ----------
if __name__ == "__main__":
    # Use eventlet or gevent in production if you want WebSocket support everywhere.
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
