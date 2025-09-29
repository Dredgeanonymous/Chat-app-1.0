# ---- app.py ----
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
    async_mode="gevent",              # match gevent worker
    logger=True,
    engineio_logger=True,
    message_queue=os.environ.get("REDIS_URL")  # OK if None
)

MOD_CODE = os.environ.get("MOD_CODE", "12345")

# -------------------------------------------------
# In-memory state (demo)
# -------------------------------------------------
# sid -> {"username": str, "role": "user"|"mod", "gender": str}
online_by_sid = {}
# simple message log (resets on redeploy)
messages = []


def online_list():
    """Unique user list across tabs, with role+gender."""
    seen = {}
    for info in online_by_sid.values():
        u = info["username"]
        seen[u] = {"role": info["role"], "gender": info.get("gender", "hidden")}
    # return list of dicts: {username, role, gender}
    return [{"username": u, **rg} for u, rg in sorted(seen.items())]


def push_online(include_self: bool = True):
    """Broadcast the roster to everyone (optionally skip sender)."""
    roster = online_list()
    socketio.emit(
        "online",
        roster,
        to=None,                                 # everyone
        skip_sid=None if include_self else request.sid
    )


def sids_for_user(username: str):
    return [sid for sid, info in online_by_sid.items() if info["username"] == username]


# -------------------------------------------------
# Socket.IO events
# -------------------------------------------------
@socketio.on("connect")
def sio_connect(auth=None):
    """On connect: register the client, send history + roster."""
    username = session.get("username", "Anon")
    if not username:
        # No flask session -> reject
        return False

    role = session.get("role", "user")
    gender = session.get("gender", "hidden")
    online_by_sid[request.sid] = {"username": username, "role": role, "gender": gender}

    # Send backlog just to this client
    emit("chat_history", messages, to=request.sid)

    # Broadcast roster to everyone (including this client once)
    push_online(include_self=True)


@socketio.on("disconnect")
def sio_disconnect():
    """On disconnect: drop from roster and broadcast."""
    online_by_sid.pop(request.sid, None)
    push_online(include_self=False)


@socketio.on("chat")
def sio_chat(data=None):
    """Public chat message."""
    user = session.get("username", "Anon")
    role = session.get("role", "user")
    gender = session.get("gender", "hidden")
    text = (data or {}).get("text", "").strip()
    if not text:
        return
    msg = {
        "id": str(len(messages) + 1),
        "username": user,
        "role": role,
        "gender": gender,
        "text": text,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    messages.append(msg)
    socketio.emit("chat", msg)  # broadcast


@socketio.on("pm")
def sio_pm(data=None):
    """Private message: {to: 'Name', text: 'hello'}"""
    sender = session.get("username", "Anon")
    text = (data or {}).get("text", "").strip()
    target = (data or {}).get("to", "").strip()
    if not text or not target or target == sender:
        return  # drop silently

    targets = sids_for_user(target)
    if not targets:
        emit("system", {"text": f"{target} is offline"}, to=request.sid)
        return

    payload = {
        "from": sender,
        "to": target,
        "text": text,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    # deliver to receiver(s)
    for sid in targets:
        emit("pm", payload, to=sid)
    # echo to sender
    emit("pm", payload, to=request.sid)


@socketio.on("delete_message")
def sio_delete_message(data=None):
    """Allow moderators to delete a message by id."""
    if session.get("role") != "mod":
        return
    mid = (data or {}).get("id")
    if not mid:
        return
    idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
    if idx is None:
        return
    removed = messages.pop(idx)
    socketio.emit("message_deleted", {"id": removed["id"]})  # broadcast


# -------------------------------------------------
# HTTP routes
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
    return send_from_directory(
        "static", "manifest.webmanifest", mimetype="application/manifest+json"
    )


@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@app.route("/", methods=["GET"])
def root():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username", "Anon") or "").strip()[:24]
        gender = (request.form.get("gender", "hidden") or "hidden").strip()
        mod_try = (request.form.get("mod_code") or "").strip()

        if not username:
            return render_template("login.html", error="Please enter a username.")

        session["username"] = username
        session["gender"] = gender
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


# -------------------------------------------------
# Entrypoint (local dev)
# -------------------------------------------------
if __name__ == "__main__":
    # In production use Gunicorn with gevent worker:
    #   gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
