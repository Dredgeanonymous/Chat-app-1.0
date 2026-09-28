# app.py — Flask + Socket.IO chat + login logging + unique usernames

import os
from datetime import datetime
from pathlib import Path
from itertools import count

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory, jsonify, Response
)
from flask_socketio import SocketIO, emit, disconnect
from markupsafe import escape

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# -----------------------------------------------------------------------------
# App / Socket.IO
# -----------------------------------------------------------------------------
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATES_DIR),
)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-secret-change-me"
)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=70,
)

# -----------------------------------------------------------------------------
# Config / Secrets
# -----------------------------------------------------------------------------
MOD_CODE = os.environ.get("MOD_CODE", "rmn")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")

# -----------------------------------------------------------------------------
# In-memory state
# -----------------------------------------------------------------------------
messages = []

# sid -> user information
online_by_sid = {}

# normalized username -> sid
sid_by_username = {}

# Stores message reactions while server is running
reaction_store = {}

# Simple in-memory login log store
_login_id = count(1)
_login_rows = []


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def next_msg_id() -> str:
    return f"m{len(messages) + 1:06d}"


def normalize_username(username: str) -> str:
    """
    Normalize usernames so Sarah, sarah and SARAH
    are treated as the same username.
    """
    return (username or "").strip().casefold()


# Jinja helper: {{ now().year }}
@app.context_processor
def inject_now():
    return {"now": datetime.utcnow}


def client_ip():
    """
    Trust X-Forwarded-For when behind a proxy/Codespaces/NGINX.
    """
    xff = request.headers.get("X-Forwarded-For")

    if xff:
        return xff.split(",")[0].strip()

    return request.remote_addr


def mask_mod_code(code: str) -> str:
    if not code:
        return ""

    if len(code) <= 2:
        return "*" * len(code)

    return "*" * (len(code) - 2) + code[-2:]


def log_login(
    username: str,
    ip: str,
    user_agent: str,
    session_id: str,
    outcome: str,
    mod_code: str
):
    row = {
        "id": next(_login_id),
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "username": (username or "").strip(),
        "ip": ip,
        "user_agent": (user_agent or "")[:300],
        "outcome": outcome,
        "mod_code_masked": mask_mod_code(mod_code or ""),
        "session_id": session_id or "",
    }

    _login_rows.append(row)

    # Keep memory bounded
    if len(_login_rows) > 1000:
        del _login_rows[:-1000]


def recent_logs(n: int = 200):
    return list(reversed(_login_rows[-n:]))


def check_auth(auth):
    return (
        auth
        and auth.username == ADMIN_USER
        and auth.password == ADMIN_PASS
    )


def require_admin():
    auth = request.authorization

    if not check_auth(auth):
        return Response(
            "Auth required",
            401,
            {
                "WWW-Authenticate":
                    'Basic realm="Login logs"'
            }
        )


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# PWA files
# -----------------------------------------------------------------------------

@app.route("/manifest.json")
@app.route("/manifest")
def manifest():
    return send_from_directory(
        "static",
        "manifest.json",
        mimetype="application/json"
    )


@app.route("/sw.js")
def sw():
    return send_from_directory(
        "static",
        "sw.js",
        mimetype="application/javascript"
    )


@app.route("/.well-known/assetlinks.json")
def assetlinks():
    return send_from_directory(
        "static/.well-known",
        "assetlinks.json",
        mimetype="application/json"
    )


# -----------------------------------------------------------------------------
# Auth / Login
# -----------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        form = request.form or {}

        username = (form.get("username") or "").strip()
        password = (form.get("password") or "").strip()
        mod_code = (form.get("mod_code") or "").strip()
        gender = (form.get("gender") or "").strip()
        avatar = (form.get("avatar") or "").strip()

        role = (
            "mod"
            if mod_code and mod_code == MOD_CODE
            else "user"
        )

        # Username is required
        ok = bool(username)

        # Log login attempt
        ip = client_ip()
        ua = request.headers.get("User-Agent", "")

        log_login(
            username=username,
            ip=ip,
            user_agent=ua,
            session_id=session.get("_id"),
            outcome="success" if ok else "failure",
            mod_code=mod_code,
        )

        if not ok:
            return render_template(
                "login.html",
                error="Username is required."
            )

        # Store login information in session
        session["username"] = username
        session["role"] = role
        session["gender"] = gender
        session["avatar"] = avatar

        return redirect(url_for("chat"))

    return render_template(
        "login.html",
        error=None
    )


# -----------------------------------------------------------------------------
# Optional JSON Login API
# -----------------------------------------------------------------------------

@app.post("/api/login")
def api_login():

    data = request.json or request.form or {}

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    mod_code = (data.get("mod_code") or "").strip()

    ip = client_ip()
    ua = request.headers.get("User-Agent", "")

    # Existing demo behavior
    ok = (
        (username == "demo" and password == "demo")
        if password
        else bool(username)
    )

    log_login(
        username=username,
        ip=ip,
        user_agent=ua,
        session_id=session.get("_id"),
        outcome="success" if ok else "failure",
        mod_code=mod_code,
    )

    if not ok:
        return jsonify({
            "ok": False,
            "error": "Invalid credentials"
        }), 401

    session["username"] = username

    return jsonify({
        "ok": True
    })


# -----------------------------------------------------------------------------
# Admin Login Logs
# -----------------------------------------------------------------------------

@app.get("/admin/logins")
def admin_logs():

    guard = require_admin()

    if guard:
        return guard

    rows = recent_logs(200)

    html = [
        "<h1>Recent login attempts</h1>",
        "<table border=1 cellpadding=6>",
        (
            "<tr>"
            "<th>ID</th>"
            "<th>Time (UTC)</th>"
            "<th>User</th>"
            "<th>IP</th>"
            "<th>User-Agent</th>"
            "<th>Outcome</th>"
            "<th>mod_code (masked)</th>"
            "</tr>"
        )
    ]

    for r in rows:

        html.append(
            f"<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{r['ts']}</td>"
            f"<td>{escape(r.get('username', ''))}</td>"
            f"<td>{escape(r.get('ip', ''))}</td>"
            f"<td>{escape((r.get('user_agent', ''))[:120])}</td>"
            f"<td>{escape(r.get('outcome', ''))}</td>"
            f"<td>{escape(r.get('mod_code_masked', ''))}</td>"
            f"</tr>"
        )

    html.append("</table>")

    return "\n".join(html)


# -----------------------------------------------------------------------------
# Chat Routes
# -----------------------------------------------------------------------------

@app.route("/chat")
def chat():

    uname = session.get("username")

    if not uname:
        return redirect(url_for("login"))

    return render_template(
        "chat.html",
        username=uname,
        role=session.get("role", "user")
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# -----------------------------------------------------------------------------
# Online Roster
# -----------------------------------------------------------------------------

def build_roster():

    roster = [
        {
            "username": info.get("username"),
            "role": info.get("role", "user"),
            "gender": info.get("gender", ""),
            "avatar": info.get("avatar", ""),
        }
        for info in online_by_sid.values()
    ]

    roster.sort(
        key=lambda r: (r["username"] or "").lower()
    )

    return roster


def broadcast_roster():
    socketio.emit(
        "online",
        build_roster()
    )


# -----------------------------------------------------------------------------
# Socket.IO Connection
# -----------------------------------------------------------------------------

@socketio.on("connect")
def sio_connect():

    # Require a logged-in session
    uname = session.get("username")

    if not uname:
        disconnect()
        return

    username_key = normalize_username(uname)

    # -------------------------------------------------------------------------
    # UNIQUE USERNAME CHECK
    # -------------------------------------------------------------------------
    #
    # If another person is already using this username,
    # tell the new person that the name is taken and disconnect them.
    #
    existing_sid = sid_by_username.get(username_key)

    if existing_sid and existing_sid != request.sid:

        emit(
            "username_taken",
            {
                "message": (
                    f'The name "{uname}" is already taken. '
                    "Please choose another name."
                )
            }
        )

        disconnect()

        return

    # -------------------------------------------------------------------------
    # Register user
    # -------------------------------------------------------------------------

    online_by_sid[request.sid] = {
        "username": uname,
        "role": session.get("role", "user"),
        "gender": session.get("gender", ""),
        "avatar": session.get("avatar", ""),
    }

    sid_by_username[username_key] = request.sid

    # Send recent chat history
    emit(
        "chat_history",
        messages[-100:]
    )

    # Update everyone else's online list
    broadcast_roster()


# -----------------------------------------------------------------------------
# Disconnect
# -----------------------------------------------------------------------------

@socketio.on("disconnect")
def sio_disconnect():

    info = online_by_sid.pop(
        request.sid,
        None
    )

    if info:

        username_key = normalize_username(
            info.get("username", "")
        )

        # Only remove the username if THIS connection owns it.
        if sid_by_username.get(username_key) == request.sid:

            sid_by_username.pop(
                username_key,
                None
            )

    broadcast_roster()


# -----------------------------------------------------------------------------
# Roster Request
# -----------------------------------------------------------------------------

@socketio.on("roster_request")
def sio_roster_request():

    emit(
        "online",
        build_roster()
    )


# -----------------------------------------------------------------------------
# Typing Indicator
# -----------------------------------------------------------------------------

@socketio.on("typing")
def handle_typing(data):

    info = online_by_sid.get(
        request.sid
    )

    if not info:
        return

    username = info.get(
        "username",
        ""
    )

    is_typing = (
        bool(data.get("typing"))
        if isinstance(data, dict)
        else False
    )

    socketio.emit(
        "typing",
        {
            "username": username,
            "typing": is_typing
        },
        skip_sid=request.sid
    )


# -----------------------------------------------------------------------------
# Public Chat
# -----------------------------------------------------------------------------

@socketio.on("chat")
def sio_chat(data):

    uname = session.get("username")

    if not uname:
        return

    txt = (data or {}).get(
        "text",
        ""
    )

    if not isinstance(txt, str):
        return

    txt = txt.strip()

    if not txt:
        return

    msg = {
        "id": next_msg_id(),
        "user": uname,
        "text": escape(txt),
        "ts": datetime.utcnow().isoformat(
            timespec="seconds"
        ) + "Z",
        "avatar": session.get(
            "avatar",
            ""
        ),
    }

    messages.append(msg)

    emit(
        "chat",
        msg,
        broadcast=True
    )


# -----------------------------------------------------------------------------
# Message Reactions
# -----------------------------------------------------------------------------

@socketio.on("react")
def handle_reaction(data):

    if not isinstance(data, dict):
        return

    message_id = str(
        data.get("id", "")
    ).strip()

    reaction = str(
        data.get("reaction", "")
    ).strip()

    allowed_reactions = {
        "👍",
        "❤️",
        "😂"
    }

    if (
        not message_id
        or reaction not in allowed_reactions
    ):
        return

    message = next(
        (
            m for m in messages
            if str(m.get("id")) == message_id
        ),
        None
    )

    if not message:
        return

    if message_id not in reaction_store:
        reaction_store[message_id] = {}

    user_reactions = reaction_store[
        message_id
    ]

    if request.sid not in user_reactions:
        user_reactions[request.sid] = set()

    reactions_by_user = user_reactions[
        request.sid
    ]

    # Toggle reaction
    if reaction in reactions_by_user:

        reactions_by_user.remove(
            reaction
        )

    else:

        reactions_by_user.add(
            reaction
        )

    # Recalculate counts
    counts = {}

    for user_set in user_reactions.values():

        for user_reaction in user_set:

            counts[user_reaction] = (
                counts.get(
                    user_reaction,
                    0
                ) + 1
            )

    # Store JSON-safe reaction counts
    message["reactions"] = counts

    socketio.emit(
        "reaction_update",
        {
            "id": message_id,
            "reactions": counts
        }
    )


# -----------------------------------------------------------------------------
# Private Messages
# -----------------------------------------------------------------------------

@socketio.on("pm")
def sio_pm(data):

    uname = session.get("username")

    if not uname:
        return

    to_user = (data or {}).get(
        "to",
        ""
    )

    txt = (data or {}).get(
        "text",
        ""
    )

    if (
        not isinstance(to_user, str)
        or not isinstance(txt, str)
    ):
        return

    to_user = to_user.strip()
    txt = txt.strip()

    if not to_user or not txt:
        return

    # Case-insensitive username lookup
    target_sid = sid_by_username.get(
        normalize_username(to_user)
    )

    if not target_sid:
        return

    target_info = online_by_sid.get(
        target_sid
    )

    if not target_info:
        return

    # Use the actual username of the recipient
    actual_to_user = target_info.get(
        "username",
        to_user
    )

    payload = {
        "from": uname,
        "to": actual_to_user,
        "text": escape(txt),
        "ts": datetime.utcnow().isoformat(
            timespec="seconds"
        ) + "Z",
        "avatar": session.get(
            "avatar",
            ""
        ),
    }

    # Send to recipient
    emit(
        "pm",
        payload,
        to=target_sid
    )

    # Echo back to sender
    emit(
        "pm",
        payload
    )


# -----------------------------------------------------------------------------
# Delete Message
# -----------------------------------------------------------------------------

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

            emit(
                "message_deleted",
                {"id": mid},
                broadcast=True
            )

            break


# -----------------------------------------------------------------------------
# WebRTC Video Calling / Signaling
# -----------------------------------------------------------------------------

@socketio.on("call_user")
def handle_call_user(data):

    caller = online_by_sid.get(
        request.sid
    )

    if not caller:
        return

    if not isinstance(data, dict):
        return

    target_username = str(
        data.get("to", "")
    ).strip()

    if not target_username:
        return

    target_sid = sid_by_username.get(
        normalize_username(target_username)
    )

    if not target_sid:

        emit(
            "call_error",
            {
                "message": (
                    f"{target_username} "
                    "is no longer online."
                )
            }
        )

        return

    emit(
        "incoming_call",
        {
            "from": caller.get(
                "username"
            ),
            "avatar": caller.get(
                "avatar",
                ""
            )
        },
        to=target_sid
    )


# -----------------------------------------------------------------------------
# Call Accepted
# -----------------------------------------------------------------------------

@socketio.on("call_accepted")
def handle_call_accepted(data):

    accepter = online_by_sid.get(
        request.sid
    )

    if not accepter:
        return

    if not isinstance(data, dict):
        return

    caller_username = str(
        data.get("from", "")
    ).strip()

    if not caller_username:
        return

    caller_sid = sid_by_username.get(
        normalize_username(
            caller_username
        )
    )

    if not caller_sid:

        emit(
            "call_error",
            {
                "message":
                    "The caller is no longer online."
            }
        )

        return

    emit(
        "call_accepted",
        {
            "from": accepter.get(
                "username"
            )
        },
        to=caller_sid
    )


# -----------------------------------------------------------------------------
# Call Rejected
# -----------------------------------------------------------------------------

@socketio.on("call_rejected")
def handle_call_rejected(data):

    rejector = online_by_sid.get(
        request.sid
    )

    if not rejector:
        return

    if not isinstance(data, dict):
        return

    caller_username = str(
        data.get("from", "")
    ).strip()

    if not caller_username:
        return

    caller_sid = sid_by_username.get(
        normalize_username(
            caller_username
        )
    )

    if not caller_sid:
        return

    emit(
        "call_rejected",
        {
            "from": rejector.get(
                "username"
            )
        },
        to=caller_sid
    )


# -----------------------------------------------------------------------------
# WebRTC Signal
# -----------------------------------------------------------------------------

@socketio.on("webrtc_signal")
def handle_webrtc_signal(data):

    sender = online_by_sid.get(
        request.sid
    )

    if not sender:
        return

    if not isinstance(data, dict):
        return

    target_username = str(
        data.get("to", "")
    ).strip()

    signal = data.get(
        "signal"
    )

    if not target_username or not signal:
        return

    target_sid = sid_by_username.get(
        normalize_username(
            target_username
        )
    )

    if not target_sid:
        return

    emit(
        "webrtc_signal",
        {
            "from": sender.get(
                "username"
            ),
            "signal": signal
        },
        to=target_sid
    )


# -----------------------------------------------------------------------------
# Call Ended
# -----------------------------------------------------------------------------

@socketio.on("call_ended")
def handle_call_ended(data):

    sender = online_by_sid.get(
        request.sid
    )

    if not sender:
        return

    if not isinstance(data, dict):
        return

    target_username = str(
        data.get("to", "")
    ).strip()

    if not target_username:
        return

    target_sid = sid_by_username.get(
        normalize_username(
            target_username
        )
    )

    if not target_sid:
        return

    emit(
        "call_ended",
        {
            "from": sender.get(
                "username"
            )
        },
        to=target_sid
    )


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------

if __name__ == "__main__":

    # Dev:
    # python app.py

    # Production:
    # gunicorn -k gevent -w 1 app:app

    socketio.run(
        app,
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )

