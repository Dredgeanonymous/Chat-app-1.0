# imports — remove the duplicate send_from_directory
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory
)

# ...

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

# ---- PWA files ----
@app.route('/manifest.json')
def manifest_json():
    # Serve the JSON with the correct MIME type
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/.well-known/assetlinks.json')
def assetlinks_file():
    return send_from_directory('static/.well-known', 'assetlinks.json', mimetype='application/json')

# ---- Auth ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        mod_code = (request.form.get("mod_code") or "").strip()
        gender   = (request.form.get("gender") or "").strip()
        avatar   = (request.form.get("avatar") or "").strip()

        if not username:
            return render_template("login.html", error="Username is required.")

        role = "mod" if mod_code and mod_code == MOD_CODE
