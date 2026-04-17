from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import csv
import time
import threading
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'adj-stroke-rehab-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# ===== LOAD CSV DATA =====
CSV_PATH = os.path.join('data', 'healthy_vitals_7months.csv')

def load_csv():
    rows = []
    try:
        with open(CSV_PATH, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        print(f"Loaded {len(rows)} rows from CSV")
    except FileNotFoundError:
        print(f"CSV file not found at {CSV_PATH}")
    return rows

csv_data = load_csv()
current_index = 0
live_data = {
    "heart_rate_bpm": 76,
    "spo2_percent": 98.0,
    "body_temperature_celsius": 36.7,
    "blood_pressure_mmhg": "114/74",
    "alert_triggered": "no",
    "alert_type": "none",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# ===== BACKGROUND THREAD — streams CSV rows in real time =====
def stream_data():
    global current_index, live_data
    while True:
        if csv_data and current_index < len(csv_data):
            row = csv_data[current_index]
            live_data = {
                "heart_rate_bpm": float(row.get("heart_rate_bpm", 76)),
                "spo2_percent": float(row.get("spo2_percent", 98)),
                "body_temperature_celsius": float(row.get("body_temperature_celsius", 36.7)),
                "blood_pressure_mmhg": row.get("blood_pressure_mmhg", "114/74"),
                "alert_triggered": row.get("alert_triggered", "no"),
                "alert_type": row.get("alert_type", "none"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            current_index += 1
            # Loop back to start when CSV ends
            if current_index >= len(csv_data):
                current_index = 0
        # Emit to all connected dashboard clients
        socketio.emit('vitals_update', live_data)
        time.sleep(2)  # Send new reading every 2 seconds

# ===== ROUTES =====
@app.route('/')
def index():
    return render_template('ADJ_StrokeRehab_Dashboard.html')

@app.route('/api/vitals', methods=['GET'])
def get_vitals():
    """REST endpoint — returns latest vitals as JSON"""
    return jsonify(live_data)

@app.route('/api/vitals', methods=['POST'])
def receive_vitals():
    """ESP8266 posts sensor data here"""
    data = request.get_json()
    if data:
        global live_data
        live_data.update({
            "heart_rate_bpm": data.get("hr", live_data["heart_rate_bpm"]),
            "spo2_percent": data.get("spo2", live_data["spo2_percent"]),
            "body_temperature_celsius": data.get("temp", live_data["body_temperature_celsius"]),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        socketio.emit('vitals_update', live_data)
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/history', methods=['GET'])
def get_history():
    """Returns last 50 readings for graph history"""
    start = max(0, current_index - 50)
    history = csv_data[start:current_index]
    return jsonify(history)

# ===== SOCKET EVENTS =====
@socketio.on('connect')
def on_connect():
    print(f"Client connected — sending current vitals")
    emit('vitals_update', live_data)

@socketio.on('disconnect')
def on_disconnect():
    print("Client disconnected")

# ===== START =====
if __name__ == '__main__':
    thread = threading.Thread(target=stream_data, daemon=True)
    thread.start()
    print("\n ADJ's Tech Industries — Stroke Rehab Monitor")
    print(" Server running at http://localhost:8080")
    print(" Open your browser and go to http://localhost:5000\n")
    socketio.run(app, host='127.0.0.1', port=8080, debug=True, use_reloader=False, log_output=True)
    
