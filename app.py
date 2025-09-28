# ---- app.py (top of file) ----
from gevent import monkey
monkey.patch_all()  # MUST be first

import os
from datetime import datetime, timezone
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory, jsonify
)
from flask_socketio import SocketIO, emit, disconnect

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",              # match your Procfile (gevent worker)
    logger=True,
    engineio_logger=True,
    message_queue=os.environ.get("REDIS_URL")  # OK if None
)


MOD_CODE = os.environ.get("MOD_CODE", "12345")
# -------------------------------------------------
# In-memory state (demo)
# -------------------------------------------------
# sid -> {"username": str, "role": "user"|"mod"}
online_by_sid = {}
# simple message log (resets on redeploy)
messages = []

def online_list():
    # Unique list; if same user opens multiple tabs, show once
    seen = {}
    for info in online_by_sid.values():
        seen[info["username"]] = info["role"]
    # return list of dicts like {"username": u, "role": r}
    return [{"username": u, "role": r} for u, r in sorted(seen.items())]

def push_online(include_self=True):
    roster = online_list()
    # Send roster to everyone (optionally include triggering client)
socketio.emit(
    "online",
    roster,
    to=None,              # send to everyone
    skip_sid=None if include_self else request.sid
)


@socketio.on("connect")
def sio_connect(auth=None):   # <— make auth optional
    username = session.get("username", "Anon")
    role = session.get("role", "user")
    online_by_sid[request.sid] = {"username": username, "role": role}

    # update roster for everyone
    push_online(include_self=True)

    # send chat history just to this new client
    socketio.emit("chat_history", messages, to=request.sid)


@socketio.on("disconnect")
def sio_disconnect():    # disconnect takes NO args
    online_by_sid.pop(request.sid, None)
    push_online(include_self=False)


@socketio.on("send_message")
def sio_send_message(data):
    text = (data or {}).get("text", "").strip()
    if not text:
        return
    msg = {
        "id": str(int(datetime.now().timestamp() * 1000)),
        "username": session.get("username", "Anon"),
        "text": text,
    }
    messages.append(msg)
    socketio.emit("message", msg, broadcast=True)

# -------------------------------------------------
# Health & debug helpers
# -------------------------------------------------
@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/api/online")
def api_online():
    return jsonify(online_list())

# PWA passthroughs
@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest", mimetype="application/manifest+json")

@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

# -------------------------------------------------
# Pages
# -------------------------------------------------
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
    return render_template("chat.html", username=session["username"], role=session.get("role", "user"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------------------------------
# Socket.IO events
# -------------------------------------------------


    username = session.get("username")
    role = session.get("role", "user")
    if not username:
        # no Flask session -> reject socket
        return False

    online_by_sid[request.sid] = {"username": username, "role": role}
    print(f"[CONNECT] {request.sid} -> {username} ({role})")

    # Send backlog to THIS client
    emit("chat_history", messages)

    # Broadcast roster to everyone (including this client, once)
    push_online(include_self=True)


    info = online_by_sid.pop(request.sid, None)
    if info:
        print(f"[DISCONNECT] {request.sid} -> {info['username']}")
    # Broadcast updated roster (including remaining clients only; sender is gone)
    push_online(include_self=False)


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
    # Explicit broadcast so ALL clients (cross-worker if Redis is set) get it
    socketio.emit("new_message", entry, broadcast=True)

@socketio.on("delete_message")
def sio_delete_message(data):
    if session.get("role") != "mod":
        return
    mid = (data or {}).get("id")
    if not mid:
        return
    idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
    if idx is None:
        return
    removed = messages.pop(idx)
    socketio.emit("message_deleted", {"id": removed["id"]}, broadcast=True)

# -------------------------------------------------
# Entrypoint (local dev)
# -------------------------------------------------
if __name__ == "__main__":
    # For local dev this is fine. In production use Gunicorn:
    #   gunicorn -k eventlet -w 1 app:app
    # If you set REDIS_URL, you may scale workers above 1.
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
