import os
from datetime import datetime, timezone
from collections import defaultdict

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory
)
from flask_socketio import SocketIO, emit, disconnect

# ----------------------
# App & Socket.IO (no eventlet)
# ----------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# ----------------------
# Config
# ----------------------
MOD_CODE = os.environ.get("MOD_CODE", "12345")  # change in Render env vars anytime

# ----------------------
# In-memory state
# ----------------------
# sid -> {"username": str, "role": "user"|"mod"}
online_by_sid: dict[str, dict] = {}

# username -> set(sid, sid, ...)
user_to_sids: defaultdict[str, set] = defaultdict(set)

# message objects for the global room
messages: list[dict] = []


def roster() -> list[dict]:
    """Unique username list with role."""
    result = {}
    for info in online_by_sid.values():
        result[info["username"]] = info["role"]
    return [{"username": u, "role": r} for u, r in sorted(result.items())]


def push_roster():
    socketio.emit("online", roster())


# ----------------------
# PWA assets passthrough
# ----------------------
@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest",
                               mimetype="application/manifest+json")


@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js",
                               mimetype="application/javascript")


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
    username = session.get("username")
    role = session.get("role", "user")
    if not username:
        # Reject sockets that don't have a Flask session
        return False

    sid = request.sid
    online_by_sid[sid] = {"username": username, "role": role}
    user_to_sids[username].add(sid)

    # Send history only to this client
    emit("history", messages)

    # Push roster to everyone
    push_roster()


@socketio.on("disconnect")
def sio_disconnect():
    sid = request.sid
    info = online_by_sid.pop(sid, None)
    if info:
        u = info["username"]
        sids = user_to_sids.get(u)
        if sids:
            sids.discard(sid)
            if not sids:
                user_to_sids.pop(u, None)
        push_roster()


@socketio.on("get_online")
def sio_get_online():
    emit("online", roster())


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
        "private": False,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    messages.append(entry)
    socketio.emit("new_message", entry)


@socketio.on("send_pm")
def sio_send_pm(data):
    """
    data = {"to": "OtherUser", "text": "..."}
    Sends a private message to all active sockets of that username,
    and echoes back to the sender's socket.
    """
    if "username" not in session:
        disconnect()
        return

    to = (data or {}).get("to", "").strip()
    text = (data or {}).get("text", "").strip()
    if not to or not text:
        return

    sender = session["username"]
    entry = {
        "id": len(messages) + 1,  # still unique server-side id
        "from": sender,
        "to": to,
        "role": session.get("role", "user"),
        "text": text,
        "private": True,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    # echo to sender
    emit("new_pm", entry, to=request.sid)

    # deliver to each active socket of the recipient
    for sid in list(user_to_sids.get(to, [])):
        socketio.emit("new_pm", entry, to=sid)


@socketio.on("mod_action")
def sio_mod_action(data):
    if session.get("role") != "mod":
        return
    if (data or {}).get("action") == "delete":
        mid = (data or {}).get("message_id")
        idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
        if idx is not None:
            removed = messages.pop(idx)
            socketio.emit("message_deleted", {"id": removed["id"]})


# ----------------------
# Run
# ----------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
