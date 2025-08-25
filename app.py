from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import mysql.connector
import random
import json
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
import numpy as np

app = Flask(__name__)  # Initialize the Flask app
CORS(app)
app.secret_key = 'devyani'
# Connect to MySQL (replace with your DB details)
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",       # your MySQL password
        database="medical_records_db"
    )
# cursor = conn.cursor(dictionary=True)
# -------------------- SIGNUP --------------------
# In the signup function, store the password in plain text
@app.route('/signup', methods=['POST'])
def signup():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    data = request.json
    name = data['name']
    email = data['email']
    phone = data['phone']
    password = data['password']  # No hashing
    gender = data['gender']

    try:
        cursor.execute("INSERT INTO users (name, email, phone, password, gender) VALUES (%s, %s, %s, %s, %s)",
                       (name, email, phone, password, gender))
        conn.commit()
        return jsonify({"message": "Signup successful"}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"message": "User with this email already exists."}), 409
    finally:
        cursor.close()
        conn.close()


# -------------------- LOGIN --------------------
@app.route('/login', methods=['POST'])
# Login handling logic with redirect
# In the login function, compare passwords in plain text
@app.route('/login', methods=['POST'])
def login():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    data = request.json
    email = data['email']
    password = data['password']

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user and user['password'] == password:  # Direct comparison with plaintext password
        session['user_id'] = user['id']
        return jsonify({"message": "Login successful", "user": {"id": user['id'], "name": user['name'], "email": user['email']}}), 200
    else:
        return jsonify({"message": "Invalid email or password"}), 401




# Logout function
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clear the session data
    return '', 204  # No content response

@app.route('/')
def home():
    return render_template('index.html')  # Loads frontend

# Global variable to store the latest blood group data
latest_blood_group_data = None

@app.route('/receive_uuid', methods=['POST'])
def receive_uuid():
    global latest_blood_group_data
    data = request.get_json()

    if not data or 'uuid' not in data:
        return jsonify({"error": "UUID not found in request"}), 400

    uuid = data['uuid']
    print(f"UUID received: {uuid}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if UUID already exists in the table
        cursor.execute("SELECT prediction_json FROM blood_group_predictions WHERE uuid = %s", (uuid,))
        result = cursor.fetchone()

        if result:
            print("🧠 Existing prediction found in DB.")
            blood_group_info = json.loads(result['prediction_json'])
        else:
            print("🎲 Generating new prediction for UUID.")
            blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
            chances = [random.randint(10, 30) for _ in range(8)]
            total = sum(chances)
            percentages = [round((c / total) * 100) for c in chances]

# Adjust so the sum is exactly 100
            diff = 100 - sum(percentages)
            percentages[0] += diff  # Add/subtract the rounding difference to the first element

            blood_group_info = dict(zip(blood_groups, percentages))


            # Insert new prediction into the database
            cursor.execute(
                "INSERT INTO blood_group_predictions (uuid, prediction_json) VALUES (%s, %s)",
                (uuid, json.dumps(blood_group_info))
            )
            conn.commit()

        cursor.close()
        conn.close()

        latest_blood_group_data = blood_group_info
        # Store both prediction and UUID
        blood_group_info['uuid'] = uuid
        latest_blood_group_data = blood_group_info

        return render_template('blood_group.html', prediction=latest_blood_group_data)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({"error": "Database error"}), 500
@app.route('/override_prediction', methods=['POST'])
def override_prediction():
    global latest_blood_group_data

    uuid = request.form.get('uuid')
    father_bg = request.form.get('father_bg')
    mother_bg = request.form.get('mother_bg')
    sibling_bg = request.form.get('sibling_bg')

    # If no family data is provided, redirect back
    if not any([father_bg, mother_bg, sibling_bg]):
        return redirect('/receive_uuid?uuid=' + uuid)

    # Build prediction purely from entered family data
    blood_group_info = {}
    if father_bg: blood_group_info[father_bg] = 33
    if mother_bg: blood_group_info[mother_bg] = 33
    if sibling_bg: blood_group_info[sibling_bg] = 34

    # Normalize to 100%
    total = sum(blood_group_info.values())
    for bg in blood_group_info:
        blood_group_info[bg] = round((blood_group_info[bg] / total) * 100)

    # Overwrite previous prediction in database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "REPLACE INTO blood_group_predictions (uuid, prediction_json) VALUES (%s, %s)",
            (uuid, json.dumps(blood_group_info))
        )
        conn.commit()

        cursor.close()
        conn.close()

        # Add source info and update global
        blood_group_info['uuid'] = uuid
        blood_group_info['source'] = 'Family inputs'
        latest_blood_group_data = blood_group_info

        return render_template('blood_group.html', prediction=blood_group_info)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({"error": "Database error"}), 500

@app.route('/basic')
def bhp():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in
    return render_template('basichealthparameters.html')
@app.route('/admin')
def admin():
    return render_template('admin.html')
@app.route('/admin1')
def admin1():
    return render_template('admin_login.html')
@app.route('/about')
def about():
    return render_template('about.html')
@app.route('/diet')
def diet():
    return render_template('diet.html')
@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')
@app.route('/login_form')
def login_page():
    return render_template('login.html')
@app.route('/dash')
def dash():
    return render_template('dash.html')
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in
    return render_template('dashboard.html')
@app.route('/latest_prediction')
def show_latest_prediction():
    return render_template('blood_group.html', prediction=latest_blood_group_data)
@app.route('/save_prediction', methods=['POST'])
def save_prediction():
    global latest_blood_group_data

    name = request.form.get('name')
    age = request.form.get('age')

    print("📦 Form received:", name, age)  # Debug print

    # For demo, associate latest prediction with UUID again
    uuid = latest_blood_group_data.get('uuid') or "unknown-uuid"

    if not all([name, age, latest_blood_group_data]):
        return render_template('blood_group.html', prediction=latest_blood_group_data, message="❌ Missing data to save.")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO saved_predictions (uuid, name, age, predictions_json)
            VALUES (%s, %s, %s, %s)
        """, (uuid, name, age, json.dumps(latest_blood_group_data)))
        conn.commit()
        cursor.close()
        conn.close()

        return render_template('blood_group.html', prediction=latest_blood_group_data, message="✅ Prediction saved successfully!")

    except Exception as e:
        return render_template('blood_group.html', prediction=latest_blood_group_data, message=f"❌ Error saving to database: {str(e)}")


cardio_data = pd.DataFrame({
    'age': np.random.randint(30, 80, 100),
    'systolic_bp': np.random.randint(90, 180, 100),
    'diastolic_bp': np.random.randint(60, 120, 100),
})
cardio_data['risk'] = ((cardio_data['systolic_bp'] > 140) | (cardio_data['diastolic_bp'] > 90)).astype(int)

X_cardio = cardio_data[['age', 'systolic_bp', 'diastolic_bp']]
y_cardio = cardio_data['risk']

cardio_model = RandomForestClassifier()
cardio_model.fit(X_cardio, y_cardio)
joblib.dump(cardio_model, 'cardiology_model.pkl')
print("✅ Saved: cardiology_model.pkl")

# ---- Neurology ----
neuro_data = pd.DataFrame({
    'memory_loss': np.random.randint(1, 11, 100),
    'reaction_time': np.random.randint(100, 4000, 100),
})
neuro_data['risk'] = ((neuro_data['memory_loss'] > 7) | (neuro_data['reaction_time'] > 2000)).astype(int)

X_neuro = neuro_data[['memory_loss', 'reaction_time']]
y_neuro = neuro_data['risk']

neuro_model = RandomForestClassifier()
neuro_model.fit(X_neuro, y_neuro)
joblib.dump(neuro_model, 'neurology_model.pkl')
print("✅ Saved: neurology_model.pkl")
cardio_model = joblib.load('cardiology_model.pkl')
neuro_model  = joblib.load('neurology_model.pkl')

@app.route('/predict_cardiology', methods=['POST'])
def predict_cardiology():
    try:
        # parse inputs
        age       = int(request.form['age'])
        systolic  = int(request.form['systolic_bp'])
        diastolic = int(request.form['diastolic_bp'])
        # prepare feature array
        X = np.array([[age, systolic, diastolic]])
        # run prediction
        pred = cardio_model.predict(X)[0]
        # map to friendly label
        label = 'At Risk' if pred else 'Normal'
        return jsonify({'prediction': label})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/predict_neurology', methods=['POST'])
def predict_neurology():
    try:
        # parse inputs
        memory_loss   = int(request.form['memory_loss'])
        reaction_time = int(request.form['reaction_time'])
        # prepare feature array
        X = np.array([[memory_loss, reaction_time]])
        # run prediction
        pred = neuro_model.predict(X)[0]
        # map to friendly label
        label = 'High Risk' if pred else 'Low Risk'
        return jsonify({'prediction': label})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
@app.route('/check_login_status', methods=['GET'])
def check_login_status():
    if 'user_id' in session:
        return jsonify({"logged_in": True})
    else:
        return jsonify({"logged_in": False})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
