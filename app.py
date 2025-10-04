app.py — Flask - Socket.IO chat - login logging (single file)

- Combines your Socket.IO chat app with the /admin/logins dashboard

- Logs username, IP, user-agent, outcome, and the mod_code (masked)

- Basic Auth protects /admin/logins (use ADMIN_USER / ADMIN_PASS env vars)

import os from datetime import datetime from pathlib import Path from itertools import count

from flask import ( Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, Response ) from flask_socketio import SocketIO, emit, disconnect from markupsafe import escape

── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(file).resolve().parent TEMPLATES_DIR = BASE_DIR / "templates" STATIC_DIR = BASE_DIR / "static"

── App / Socket.IO (define before any decorators) ────────────────────────────

app = Flask( name, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATES_DIR), ) app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

socketio = SocketIO( app, cors_allowed_origins="*", ping_interval=25, ping_timeout=70, )

── Config / Secrets ─────────────────────────────────────────────────────────

MOD_CODE = os.environ.get("MOD_CODE", "letmein") ADMIN_USER = os.environ.get("ADMIN_USER", "admin") ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")  # change in env!

── In-memory state (demo) ───────────────────────────────────────────────────

messages = []          # [{id, user, text, ts, avatar?}] online_by_sid = {}     # sid -> {"username","role","gender","avatar"} sid_by_username = {}   # username -> sid

Simple in-memory login log store

_login_id = count(1) _login_rows = []  # [{id, ts, username, ip, user_agent, outcome, mod_code_masked}]

def next_msg_id() -> str: return f"m{len(messages)+1:06d}"

Jinja helper: {{ now().year }}

@app.context_processor def inject_now(): return {"now": datetime.utcnow}

─────────────────────────────── Helpers ──────────────────────────────────────

def client_ip(): """Trust X-Forwarded-For when behind a proxy/Codespaces/NGINX.""" xff = request.headers.get("X-Forwarded-For") if xff: return xff.split(",")[0].strip() return request.remote_addr

def mask_mod_code(code: str) -> str: if not code: return "" if len(code) <= 2: return "" * len(code) return "" * (len(code) - 2) + code[-2:]

def log_login(username: str, ip: str, user_agent: str, session_id: str, outcome: str, mod_code: str): row = { "id": next(_login_id), "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z", "username": (username or "").strip(), "ip": ip, "user_agent": (user_agent or "")[:300], "outcome": outcome, "mod_code_masked": mask_mod_code(mod_code or ""), "session_id": session_id, } _login_rows.append(row) # trim to last 1000 rows to keep memory bounded if len(_login_rows) > 1000: del _login_rows[:-1000]

def recent_logs(n: int = 200): return list(reversed(_login_rows[-n:]))

def check_auth(auth): return auth and auth.username == ADMIN_USER and auth.password == ADMIN_PASS

def require_admin(): auth = request.authorization if not check_auth(auth): return Response( "Auth required", 401, {"WWW-Authenticate": 'Basic realm="Login logs"'} )

───────────────────────────────── Routes ─────────────────────────────────────

@app.route("/") def root(): return redirect(url_for("landing"))

@app.route("/landing") def landing(): return render_template("landing.html")

@app.route("/privacy") def privacy(): return render_template("privacy.html")

@app.route("/terms") def terms(): return render_template("terms.html")

@app.route("/cookies") def cookies(): return render_template("cookies.html")

---- PWA files (match base.html calls url_for('manifest') and url_for('sw')) --

@app.route("/manifest.json") @app.route("/manifest") def manifest(): return send_from_directory("static", "manifest.json", mimetype="application/json")

@app.route("/sw.js") def sw(): return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/.well-known/assetlinks.json") def assetlinks(): return send_from_directory("static/.well-known", "assetlinks.json", mimetype="application/json")

---- Auth / Chat (merged with login logging) ---------------------------------

@app.route("/login", methods=["GET", "POST"]) def login(): """Login form used by the chat app, now also logs attempts. - If your template includes a password field, we'll read it; otherwise it stays empty. - Outcome is considered 'success' if a username was provided (to match prior behavior). - Role becomes 'mod' if mod_code matches MOD_CODE. """ if request.method == "POST": form = request.form or {} username = (form.get("username") or "").strip() password = (form.get("password") or "").strip()  # optional in UI mod_code  = (form.get("mod_code") or "").strip() gender    = (form.get("gender") or "").strip() avatar    = (form.get("avatar") or "").strip()

role = "mod" if (mod_code and mod_code == MOD_CODE) else "user"

    # Consider 'success' if username given (keeps existing flow working)
    ok = bool(username)

    # Log the attempt regardless of success
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
        return render_template("login.html", error="Username is required.")

    # Persist session for chat
    session["username"] = username
    session["role"] = role
    session["gender"] = gender
    session["avatar"] = avatar
    return redirect(url_for("chat"))

return render_template("login.html", error=None)

@app.post("/api/login") def api_login(): """Optional JSON API for login that also logs (useful for mobile clients).""" data = request.json or request.form or {} username = (data.get("username") or "").strip() password = (data.get("password") or "").strip() mod_code = (data.get("mod_code") or "").strip()

ip = client_ip()
ua = request.headers.get("User-Agent", "")

# Dummy check retained from your snippet; adjust as needed
ok = (username == "demo" and password == "demo") if password else bool(username)

log_login(
    username=username,
    ip=ip,
    user_agent=ua,
    session_id=session.get("_id"),
    outcome="success" if ok else "failure",
    mod_code=mod_code,
)

if not ok:
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401

session["user"] = username
return jsonify({"ok": True})

@app.get("/admin/logins") def admin_logs(): guard = require_admin() if guard: return guard  # prompts for Basic Auth rows = recent_logs(200) # simple HTML table html = [ "<h1>Recent login attempts</h1>", "<table border=1 cellpadding=6>", "<tr><th>ID</th><th>Time (UTC)</th><th>User</th><th>IP</th><th>User-Agent</th><th>Outcome</th><th>mod_code (masked)</th></tr>", ] for r in rows: html.append( f"<tr><td>{r['id']}</td><td>{r['ts']}</td><td>{r['username'] or ''}</td>" f"<td>{r['ip'] or ''}</td><td>{(r['user_agent'] or '')[:120]}</td>" f"<td>{r['outcome']}</td><td>{r['mod_code_masked'] or ''}</td></tr>" ) html.append("</table>") return "\n".join(html)

@app.route("/chat") def chat(): uname = session.get("username") if not uname: return redirect(url_for("login")) return render_template("chat.html", username=uname, role=session.get("role", "user"))

@app.route("/logout") def logout(): session.clear() return redirect(url_for("login"))

───────────────────────────── Socket.IO events ───────────────────────────────

def build_roster(): roster = [{ "username": info.get("username"), "role": info.get("role", "user"), "gender": info.get("gender", ""), "avatar": info.get("avatar", ""), } for info in online_by_sid.values()] roster.sort(key=lambda r: (r["username"] or "").lower()) return roster

def broadcast_roster(): socketio.emit("online", build_roster())

@socketio.on("connect") def sio_connect(): # Require a logged-in session for sockets uname = session.get("username") if not uname: disconnect() return

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

@socketio.on("disconnect") def sio_disconnect(): info = online_by_sid.pop(request.sid, None) if info: sid_by_username.pop(info.get("username"), None) broadcast_roster()

@socketio.on("roster_request") def sio_roster_request(): # Client calls this right after (re)connect to fill the Online list emit("online", build_roster())

@socketio.on("typing") def sio_typing(data): uname = session.get("username") if not uname: return emit( "typing", {"user": uname, "typing": bool((data or {}).get("typing"))}, broadcast=True, include_self=False, )

@socketio.on("chat") def sio_chat(data): uname = session.get("username") if not uname: return txt = (data or {}).get("text", "").strip() if not txt: return

msg = {
    "id": next_msg_id(),
    "user": uname,
    "text": escape(txt),
    "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    "avatar": session.get("avatar", ""),
}
messages.append(msg)
emit("chat", msg, broadcast=True)

@socketio.on("pm") def sio_pm(data): uname = session.get("username") if not uname: return to_user = (data or {}).get("to", "").strip() txt = (data or {}).get("text", "").strip() if not to_user or not txt: return

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

@socketio.on("delete_message") def sio_delete_message(data): if session.get("role", "user") != "mod": return mid = (data or {}).get("id") if not mid: return for i, m in enumerate(messages): if m["id"] == mid: messages.pop(i) emit("message_deleted", {"id": mid}, broadcast=True) break

── Entrypoint ────────────────────────────────────────────────────────────────

if name == "main": # Dev: python app.py # Prod (Render): gunicorn -k gevent -w 1 app:app socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

