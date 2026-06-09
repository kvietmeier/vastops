import pandas as pd
import numpy as np
import time
import uuid
import os
import random
from datetime import datetime

# --- CONFIGURATION ---
# Based on your logs, your path is:
DATA_PATH = "/mount/vast"
os.makedirs(DATA_PATH, exist_ok=True)

def generate_data():
    counter = 0
    while True:
        now = datetime.now()
        
        # --- DEMO LOGIC: HIGH ACTION ---
        # 33% chance = Approx one error every 3 seconds
        is_suspicious = np.random.random() < 0.1
        
        tx = [{
            'id': str(uuid.uuid4())[:8],
            'time': now.strftime("%H:%M:%S"),
            # Suspicious = High Value ($500k+), Clean = Low Value
            'amount': np.random.randint(500_000, 5_000_000) if is_suspicious else np.random.randint(100, 50_000),
            'country': np.random.choice(['PRK', 'IRN', 'RUS']) if is_suspicious else 'GBR',
            'status': 'RED_FLAG' if is_suspicious else 'CLEAN'
        }]
        
        # Write to Parquet
        df = pd.DataFrame(tx)
        filename = f"{DATA_PATH}/tx_{int(time.time()*1000)}.parquet"
        df.to_parquet(filename)
        
        # Visual feedback for the person recording
        if is_suspicious:
            print(f"[{now.strftime('%H:%M:%S')}] 🚨 Wrote SUSPICIOUS batch -> {filename}")
        else:
            print(f"[{now.strftime('%H:%M:%S')}] ✅ Wrote clean batch      -> {filename}")
        
        # --- TIMING ---
        # Fast 1-second interval keeps the dashboard "Live Feed" scrolling constantly
        time.sleep(1.0)

if __name__ == "__main__":
    print("--- 🏦 GCP TRADING FLOOR LIVE (High Velocity Demo Mode) ---")
    print("--- ⚡ Speed: 1 batch/sec | 💀 Error Rate: ~33% ---")
    generate_data()
