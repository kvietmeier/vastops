from flask import Flask, render_template, jsonify
import pandas as pd
import glob
import os
import time

app = Flask(__name__)

# --- CONFIGURATION ---
# Based on your previous error logs, your path is likely:
DATA_PATH = "/mount/vast"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    # 1. READ VAST DATA
    # Find all parquet files
    try:
        files = glob.glob(f"{DATA_PATH}/*.parquet")
    except Exception as e:
        return jsonify({"status": "ERROR", "error": str(e)})

    if not files:
        return jsonify({"volume": "$0", "alert_count": 0, "status": "WAITING_FOR_DATA", "recent_tx": [], "alerts": []})
    
    # Sort and take the last 10 files to show "Live" window
    files.sort(key=os.path.getmtime)
    recent_files = files[-10:]
    
    try:
        df = pd.concat([pd.read_parquet(f) for f in recent_files])
    except:
        return jsonify({"volume": "$0", "alert_count": 0, "status": "WAITING_FOR_DATA", "recent_tx": [], "alerts": []})

    # 2. CALCULATE METRICS
    total_vol = float(df['amount'].sum())
    
    # Filter for BAD ACTORS
    alerts = df[df['status'] == 'RED_FLAG'].to_dict(orient='records')
    recent_tx = df.tail(10).iloc[::-1].to_dict(orient='records') # For the scrolling list

    # 3. DETERMINE SYSTEM STATUS
    system_status = "CRITICAL" if len(alerts) > 0 else "SECURE"

    return jsonify({
        "volume": f"${total_vol:,.0f}",
        "alert_count": len(alerts),
        "status": system_status,
        "recent_tx": recent_tx,
        "alerts": alerts
    })

if __name__ == '__main__':
    # We keep the 0.0.0.0 fix so you can still access it externally
    print("--- 🛡️ ORIGINAL DASHBOARD STARTED (Manual Reset Mode) ---")
    app.run(host='0.0.0.0', port=5000, debug=True)
