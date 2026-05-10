from flask import render_template, request, redirect, url_for
from website.session import *
from model import *
from flask import flash
from flask import send_file
import os
from flask import request, jsonify
from openai import OpenAI # type: ignore
from datetime import datetime, timedelta
import joblib
import numpy as np   
import serial
import time


client = OpenAI(api_key="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")

ser = None

def init_serial():
    global ser
    if ser is None:
        try:
            ser = serial.Serial("COM7", 9600, timeout=1)
            time.sleep(2)
        except:
            ser = None

def parse_line(line):
    try:
        data = {}
        parts = line.strip().split(",")

        for p in parts:
            k, v = p.split(":")
            k = k.strip()
            v = v.strip()

            if k == "PH":
                data["ph"] = float(v)

        return data if data else None
    except:
        return None


def register_routes(app):
    
    @app.route("/")
    def index():
        return redirect(url_for("home"))

    @app.route("/home")
    def home():
        if not is_login():
            return redirect(url_for("login"))

        if is_admin():
            return redirect("/admin_users")

        return render_template("home.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            user = login_user(email, password)

            if user:
                set_login(True)
                set_user_id(user["id"])
                set_user_name(user["name"])
                set_user_role(user["role"])
                return redirect("/")

            flash("Invalid email or password")

        return render_template("login.html")
  
    @app.route("/logout")
    def logout_page():
        logout()
        return redirect("/")        
    
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")
            confirm = request.form.get("confirm")
            birth_date = request.form.get("birth_date")

            if not name or not email or not password or not confirm or not birth_date:
                flash("All fields are required")
                return redirect("/register")

            if not name.replace(" ", "").isalpha():
                flash("Name must contain only letters")
                return redirect("/register")

            import re
            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                flash("Invalid email format")
                return redirect("/register")

            if len(password) < 8:
                flash("Password must be at least 8 characters")
                return redirect("/register")

            if password != confirm:
                flash("Passwords do not match")
                return redirect("/register")

            success = create_user(name, email, password, "patient", birth_date)

            if not success:
                flash("Email already exists")
                return redirect("/register")

            user = login_user(email, password)
            set_login(True)
            set_user_id(user["id"])
            set_user_name(user["name"])
            set_user_role(user["role"])
            return redirect("/")                

        return render_template("register.html")    
    
    @app.route("/forgot_password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            email = request.form.get("email")

            if not email:
                flash("Email is required")
                return redirect("/forgot_password")

            import re
            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                flash("Invalid email format")
                return redirect("/forgot_password")

            success = create_reset_token(email)

            flash("If this email exists, a reset link was sent")
            return redirect("/login")

        return render_template("forgot_password.html")

    @app.route("/reset_password/<token>", methods=["GET", "POST"])
    def reset_password_page(token):
        if request.method == "POST":
            password = request.form.get("password")
            confirm = request.form.get("confirm")

            if not password or not confirm:
                flash("All fields are required")
                return redirect(request.url)

            if len(password) < 8:
                flash("Password must be at least 8 characters")
                return redirect(request.url)

            if password != confirm:
                flash("Passwords do not match")
                return redirect(request.url)

            success = reset_password(token, password)

            if not success:
                flash("Invalid or expired link")
                return redirect("/login")

            flash("Password updated successfully")
            return redirect("/login")

        return render_template("reset_password.html")    

    @app.route("/profile")
    def profile():
        if not is_login():
            return redirect("/login")
        return render_template("profile.html")

    @app.route("/update_profile", methods=["GET", "POST"])
    def update_profile():
        if not is_login():
            return redirect("/login")

        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            birth_date = request.form.get("birth_date")

            update_user_profile(get_user_id(), name, email, birth_date)
            set_user_name(name)

            flash("Profile updated")
            return redirect("/profile")

        user = get_user_by_id(get_user_id())
        return render_template("update_profile.html", user=user)

    @app.route("/update_password", methods=["GET", "POST"])
    def update_password():
        if not is_login():
            return redirect("/login")

        if request.method == "POST":
            old = request.form.get("old_password")
            new = request.form.get("new_password")
            confirm = request.form.get("confirm_password")

            if not old or not new or not confirm:
                flash("All fields required")
                return redirect("/update_password")

            if len(new) < 8:
                flash("Password must be at least 8 characters")
                return redirect("/update_password")

            if new != confirm:
                flash("Passwords do not match")
                return redirect("/update_password")

            ok = update_user_password(get_user_id(), old, new)

            if not ok:
                flash("Old password incorrect")
                return redirect("/update_password")

            flash("Password updated successfully")
            return redirect("/profile")

        return render_template("update_password.html") 

    @app.route("/feedback", methods=["GET", "POST"])
    def feedback():
        if not is_login():
            return redirect("/login")

        questions = get_all_questions()

        if request.method == "POST":
            answers = {}

            for q in questions:
                qid = str(q[0]).strip()
                key = f"q_{qid}"
                val = request.form.get(key)

                if val is None or val.strip() == "":
                    flash("Please answer all questions")
                    return redirect("/feedback")

                answers[qid] = val

            save_feedback(get_user_id(), answers)

            flash("Feedback submitted")
            return redirect("/home")

        return render_template("feedback.html", questions=questions)    

    @app.route("/admin_users")
    def admin_users():
        if not is_admin():
            return redirect("/login")

        search = request.args.get("q", "").lower()

        users = get_all_users()

        if search:
            users = [u for u in users if search in u[1].lower()]

        return render_template("admin_users.html", users=users, search=search)

    @app.route("/admin_tests")
    def admin_tests():
        if not is_admin():
            return redirect("/")

        selected_date = request.args.get("date")
        search = request.args.get("q", "").lower()

        if not selected_date:
            selected_date = datetime.now().strftime("%Y-%m-%d")

        conn = get_connection()

        tests = get_all_tests_by_date(selected_date)
        cursor = conn.cursor()

        new_tests = []
        for t in tests:
            cursor.execute("SELECT name FROM users WHERE id = ?", (t[4],))
            user = cursor.fetchone()
            username = user[0] if user else "Unknown"

            if search and search not in username.lower():
                continue

            new_tests.append(t + (username,))

        conn.close()
        tests = new_tests        

        days = []
        for i in range(7):
            d = datetime.now() - timedelta(days=6-i)
            days.append({
                "date": d.strftime("%Y-%m-%d"),
                "day": d.strftime("%d"),
                "name": d.strftime("%a")
            })

        return render_template(
            "admin_tests.html",
            tests=tests,
            days=days,
            selected_date=selected_date,
            search=search
        )
        
    @app.route("/admin_feedback")
    def admin_feedback():
        if not is_admin():
            return redirect("/login")

        feedbacks = get_feedback_grouped()

        return render_template("admin_feedback.html", feedbacks=feedbacks)

    @app.route("/chat_api", methods=["POST"])
    def chat_api():
        data = request.json
        user_msg = data.get("message", "")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant for a UTI monitoring system. Help users understand urine test results (leukocytes, nitrite, blood, protein, pH). Explain simply."
                },
                {
                    "role": "user",
                    "content": user_msg
                }
            ]
        )

        reply = response.choices[0].message.content

        return jsonify({"reply": reply})    
    
    @app.route("/chat")
    def chat():
        if not is_login():
            return redirect("/login")

        return render_template("chat.html")    

    @app.route("/results")
    def results():
        if not is_login():
            return redirect("/login")

        user_id = get_user_id()

        selected_date = request.args.get("date")
        if not selected_date:
            selected_date = datetime.now().strftime("%Y-%m-%d")

        tests = get_tests_by_date(user_id, selected_date)

        days = []
        for i in range(7):
            d = datetime.now() - timedelta(days=6-i)
            days.append({
                "date": d.strftime("%Y-%m-%d"),
                "day": d.strftime("%d"),
                "name": d.strftime("%a")
            })

        return render_template(
            "results.html",
            tests=tests,
            days=days,
            selected_date=selected_date
        )

    @app.route("/new_test")
    def new_test():
        if not is_login():
            return redirect("/login")
        return render_template("new_test.html")

    @app.route("/predict", methods=["POST"])
    def predict_api():
        if not is_login():
            return {"error": "Unauthorized"}, 401

        data = request.json or {}

        try:
            leukocytes = float(data.get("leukocytes"))
            nitrite = float(data.get("nitrite"))
            blood = float(data.get("blood"))
            protein = float(data.get("protein"))
            ph = float(data.get("ph"))
        except:
            return {"error": "Invalid input"}, 400

        probability, color = model_predict(
            leukocytes, nitrite, blood, protein, ph
        )

        patient_id = get_user_id()

        test_id = add_test_full(
            patient_id,
            leukocytes,
            nitrite,
            blood,
            protein,
            ph,
            probability,
            color
        )

        return {
            "test_id": test_id,
            "probability": probability,
            "color": color
        }

    @app.route("/result_info/<int:test_id>")
    def result_info(test_id):
        if not is_login():
            return redirect("/login")

        t = get_test_with_recommendation(test_id)

        return render_template("result_info.html", t=t)

    ##model
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MODEL_PATH = os.path.join(BASE_DIR, "model", "uti_model.pkl")
    model = joblib.load(MODEL_PATH)

    def model_predict(leukocytes, nitrite, blood, protein, ph):
        import pandas as pd

        X = pd.DataFrame([{
            "leukocytes": float(leukocytes),
            "nitrite": int(nitrite),
            "blood": float(blood),
            "protein": float(protein),
            "ph": float(ph)
        }])

        prob = float(model.predict_proba(X)[0][1])

        if prob >= 0.75:
            color = "red"
        elif prob >= 0.25:
            color = "yellow"
        else:
            color = "green"  

        return round(prob, 3), color

    @app.route("/read_device")
    def read_device():
        global ser
        init_serial()

        if ser is None:
            return {"error": "device not connected"}, 500

        try:
            for _ in range(10):
                line = ser.readline().decode(errors="ignore")
                if not line:
                    continue

                data = parse_line(line)
                if data:
                    return data

            return {"error": "no data"}, 400

        except Exception as e:
            return {"error": str(e)}, 500