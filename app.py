import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")  # no eventlet

MOD_CODE = os.environ.get("MOD_CODE", "12345")

# In-memory state
online_by_sid = {}      # sid -> {"username": str, "role": "user"|"mod"}
messages = []           # list of dicts

def online_list():
    return [{"username": v["username"], "role": v["role"]} for v in online_by_sid.values()]

def push_online():
    socketio.emit("online", online_list())

# ---- PWA passthroughs (optional, harmless if files exist) ----
@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js")

# ---- pages ----
@app.route("/", methods=["GET"])
def root():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_try = (request.form.get("mod_code") or "").strip()
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
    return render_template("chat.html", username=session["username"], role=session.get("role","user"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# REST helper so front-end can fetch roster once on load
@app.route("/api/online")
def api_online():
    return jsonify(online_list())

# ---- Socket.IO ----
@socketio.on("connect")
def sio_connect():
    username = session.get("username")
    role = session.get("role", "user")
    if not username:
        return False  # reject
    online_by_sid[request.sid] = {"username": username, "role": role}
    emit("history", messages)           # send backlog to just this client
    push_online()                       # update everyone

@socketio.on("disconnect")
def sio_disconnect():
    online_by_sid.pop(request.sid, None)
    push_online()

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
        "ts": datetime.now(timezone.utc).isoformat()
    }
    messages.append(entry)
    socketio.emit("new_message", entry)  # to all clients

@socketio.on("mod_action")
def sio_mod_action(data):
    if session.get("role") != "mod":
        return
    action = (data or {}).get("action")
    if action == "delete":
        mid = (data or {}).get("message_id")
        idx = next((i for i, m in enumerate(messages) if m["id"] == mid), None)
        if idx is not None:
            removed = messages.pop(idx)
            socketio.emit("message_deleted", {"id": removed["id"]})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
