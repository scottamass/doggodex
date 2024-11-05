# app.py
from flask import Flask, render_template, redirect, request, session, url_for, jsonify
from functools import wraps
from supabase_client import supabase
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

# Decorator to restrict access to protected pages
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("supabase_token"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function

# Public Homepage
@app.route("/")
def home():
    return render_template("home.html")

# Login Page
@app.route("/login")
def login_page():
    return render_template("login.html")

# GitHub OAuth Sign-in
@app.route("/signin/github")
def signin_with_github():
    res = supabase.auth.sign_in_with_oauth(
        {
            "provider": "github",
            "options": {
                "redirect_to": f"{request.host_url}callback"
            },
        }
    )
    return redirect(res.url)

# Callback after GitHub OAuth
@app.route("/callback")
def callback():
    code = request.args.get("code")
    print(code)
    next_page = request.args.get("next", "/protected")

    if code:
        res = supabase.auth.exchange_code_for_session({"auth_code": code})
        print(res.session.access_token)
        user = supabase.auth.get_user(res.session.access_token)
        print(user)
        session["supabase_token"] = res.session.access_token

    return redirect(next_page)

# Email/Password Sign-up
@app.route("/signup", methods=["POST"])
def signup():
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        supabase.auth.sign_up({"email": email, "password": password})
        return redirect(url_for("login_page"))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Email/Password Login
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        session["supabase_token"] = res.session.access_token
        return redirect(url_for("protected_page"))
    except Exception as e:
        return jsonify({"error": str(e)}), 401

# Protected Route
@app.route("/protected")
@login_required
def protected_page():
    # return render_template("protected.html")
    return 'protected'

# Logout
@app.route("/logout")
def logout():
    supabase.auth.sign_out()
    session.pop("supabase_token", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
