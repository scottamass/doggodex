# app.py
from datetime import timedelta
from flask import Flask, render_template, redirect, request, session, url_for, jsonify
from flask_login import LoginManager, current_user, login_user, login_required, logout_user, UserMixin
from functools import wraps

from supabase import AuthApiError
import torch
from supabase_client import supabase
import os
from transformers import ViTForImageClassification, ViTImageProcessor
import torch
from PIL import Image
import io
import base64
import torch.nn.functional as F
# Load the model and processor
device = "cuda" if torch.cuda.is_available() else "cpu"
from transformers import AutoImageProcessor, AutoModelForImageClassification

processor = AutoImageProcessor.from_pretrained("jhoppanne/Dogs-Breed-Image-Classification-V2")
model = AutoModelForImageClassification.from_pretrained("jhoppanne/Dogs-Breed-Image-Classification-V2")
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
        print('working')
        return User(user_id, user.user.id) if user else None
    except AuthApiError as e:
        print(e)
        if "token is expired" in str(e):
            # Handle expired token - try refreshing
            try:
                print(f'refreshing Token for: ')
                refresh_response = supabase.auth.refresh_session(session['refresh'])
                # print(refresh_response)
                new_access_token = refresh_response.session.access_token
                print(new_access_token)
                user = supabase.auth.get_user(new_access_token)
                session['_user_id']=new_access_token
                session['refresh']=refresh_response.session.refresh_token
                return User(new_access_token, user.user.id) if user else None
            except Exception as refresh_error:
                print("Token refresh failed:", refresh_error)
                logout_user()
        else:
            print("AuthApiError:", e)

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
@app.route('/camera')
def camera():
    return render_template('camera.html')
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
    
    next_page = request.args.get("next", "/protected")

    if code:
        res = supabase.auth.exchange_code_for_session({"auth_code": code})
        
        jwt = res.session.access_token
        user = supabase.auth.get_user(res.session.access_token)
      
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

@app.route('/capture', methods=['POST'])
def capture():
    data = request.json.get('image_data')
    if data:
        # Decode the Base64 image data
        image_data = base64.b64decode(data)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        # Preprocess the image and make a prediction
        inputs = processor(images=image, return_tensors='pt').to(device)
        outputs = model(**inputs)

        # Calculate confidence level
        probabilities = F.softmax(outputs.logits, dim=-1)
        confidence, predicted_id = torch.max(probabilities, dim=-1)
        predicted_pokemon = model.config.id2label[predicted_id.item()]
        confidence_percentage = confidence.item() * 100

        # Print the predicted Pokémon and confidence level
        print(f"Predicted Pokémon: {predicted_pokemon}, Confidence: {confidence_percentage:.2f}%")
        
        # Conditional response based on confidence level
        if confidence_percentage < 10:
            return jsonify({
                "predicted_pokemon": 'I am unable to find a doggo',
                "confidence": confidence_percentage
            })
        else:
            return jsonify({
                "predicted_pokemon": predicted_pokemon,
                "confidence": confidence_percentage
            })
    
    return jsonify({"error": "No image data received"}), 400

if __name__ == "__main__":
    app.run(debug=True)
