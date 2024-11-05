# app.py
from datetime import timedelta
from flask import Flask, render_template, redirect, request, session, url_for, jsonify
from flask_login import LoginManager, current_user, login_user, login_required, logout_user, UserMixin
from functools import wraps

from supabase import AuthApiError
from supabase_client import supabase
import os

app = Flask(__name__)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

# Setup Flask-Login
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, uid):
        self.id = id
        self.uid = uid
       

# @login_manager.user_loader
# def load_user(user_id):
#     # print(f'-------{user_id}---------')
#     print(f'-------{user_id}---------')
#     user = supabase.auth.get_user(user_id)
#     print(user)
#     if user:
#         return User(id=user,uid=user.user.id)
#     return None


@login_manager.user_loader
def load_user(user_id):
    try:
        user = supabase.auth.get_user(user_id)
    except AuthApiError as e:
        if "token is expired" in str(e):
            # Handle expired token - try refreshing
            try:

                refresh_response = supabase.auth.refresh_session(session['refresh'])
                print(refresh_response)
                new_access_token = refresh_response.session.access_token
                user = supabase.auth.get_user(new_access_token)
            except Exception as refresh_error:
                print("Token refresh failed:", refresh_error)
                logout_user()
        else:
            print("AuthApiError:", e)
    return User(user.sid, user.user.id) if user else None

# Decorator to restrict access to protected pages
# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if not session.get("supabase_token"):
#             return redirect(url_for("login_page"))
#         return f(*args, **kwargs)
#     return decorated_function

# Public Homepage
@app.route("/")
def home():
    if session:
        print(session['refresh'])
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
        jwt = res.session.access_token
        user = supabase.auth.get_user(res.session.access_token)
        print(user)
        refresh = res.session.refresh_token
        session['refresh']=refresh
        session.permanent=True
        user = User(jwt,user.user.id)
        login_user(user)

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
        jwt = res.session.access_token
        refresh = res.session.refresh_token
        session['refresh']=refresh
        session.permanent=True
        user = res.user.id

        user = User(jwt,user)
        login_user(user)
        return redirect(url_for("protected_page"))
    except Exception as e:
        return jsonify({"error": str(e)}), 401

# Protected Route
@app.route("/protected")
@login_required
def protected_page():
    return render_template("protected.html")
  

# Logout
@app.route("/logout")
def logout():
    # supabase.auth.sign_out()
    # session.pop("supabase_token", None)
    logout_user()
    session.pop("session", None)
    supabase.auth.sign_out()

    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
