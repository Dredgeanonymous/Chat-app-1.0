# app.py — Flask + Socket.IO (threading) chat, production-ready for Render/Railway/Fly
import os
import itertools
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, disconnect
from werkzeug.middleware.proxy_fix import ProxyFix

# ---------------- App & Socket.IO config ----------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret")

# If you want to restrict CORS in production, set ALLOWED_ORIGINS to your site URL.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

socketio = SocketIO(
    app,
    async_mode="threading",           # no eventlet/gevent
    cors_allowed_origins=ALLOWED_ORIGINS,
    ping_timeout=25,
    ping_interval=10,
)

# When running behind a proxy/load balancer (Render, Railway, Fly)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# ---------------- App settings ----------------
MOD_ACCESS_CODE = os.getenv("MOD_ACCESS_CODE", "9999")  # change in dashboard/env

# ---------------- In-memory state (resets on restart) ----------------
messages = []                              # [{id, username, role, text, ts}]
_next_id = itertools.count(1)
online = {}                                # sid -> {"username":..., "role":...}
MAX_HISTORY = 300

def utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def push_user_list():
    """Build and broadcast the current online list (deduped by username)."""
    by_name = {}
    for u in online.values():
        name, role = u["username"], u["role"]
        if name not in by_name or role == "mod":
            by_name[name] = role
    users = [{"username": n, "role": r} for n, r in sorted(by_name.items())]
    socketio.emit("user_list", users)

# ---------------- Routes ----------------
@app.route("/")
def home():
    return redirect(url_for("chat") if "username" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_code = (request.form.get("mod_code") or "").strip()
        if not username:
            return render_template("login.html", error="Please enter a username.")
        role = "mod" if mod_code == MOD_ACCESS_CODE else "user"
        session["username"] = username
        session["role"] = role
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

@app.route("/healthz")
def healthz():
    return {"ok": True, "users_online": len(online), "messages": len(messages)}

# ---------------- Socket.IO events ----------------
@socketio.on("connect")
def on_connect():
    """
    Accept connection only if HTTP session exists.
    Send chat history to just this client, and add to online list.
    """
    username = session.get("username")
    role = session.get("role", "user")
    if not username:
        # No session -> reject socket (prevents anonymous connections)
        return False

    online[request.sid] = {"username": username, "role": role}

    # Send only to this client
    emit("chat_history", list(messages)[-100:])

    # Notify everyone about current online users
    push_user_list()

@socketio.on("disconnect")
def on_disconnect():
    online.pop(request.sid, None)
    push_user_list()

@socketio.on("send_message")
def on_send_message(data):
    username = session.get("username")
    role = session.get("role", "user")
    text = (data or {}).get("text", "").strip()
    if not username or not text:
        return
    m = {
        "id": next(_next_id),
        "username": username,
        "role": role,
        "text": text[:2000],
        "ts": utc_iso(),
    }
    messages.append(m)
    # keep history small
    if len(messages) > MAX_HISTORY:
        del messages[: len(messages) - MAX_HISTORY]

    # Broadcast to everyone (no broadcast= kw in modern python-socketio)
    socketio.emit("new_message", m)

@socketio.on("delete_message")
def on_delete_message(data):
    # Moderator-only
    if session.get("role") != "mod":
        return
    try:
        mid = int((data or {}).get("id"))
    except Exception:
        return
    for i, m in enumerate(messages):
        if m["id"] == mid:
            messages.pop(i)
            socketio.emit("message_deleted", {"id": mid})
            break

@socketio.on("refresh")
def on_refresh(_=None):
    push_user_list()

# ---------------- Run (production entry) ----------------
if __name__ == "__main__":
    # Most platforms inject PORT; default to 5000 for local dev
    port = int(os.getenv("PORT", "5000"))
    # 0.0.0.0 so the platform’s router can reach it
    socketio.run(app, host="0.0.0.0", port=port, debug=False)