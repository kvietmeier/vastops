#!/usr/bin/env python3
"""
Copyright 2026 Karl V.
Licensed under the Apache License, Version 2.0 (the "License");

Can be used for monitoring replication status of VAST nodes by 
periodically checking TCP connectivity to specified ports. 
Logs results to a CSV file for later analysis.

=== EXAMPLE USAGE SUMMARY ===
1. Primary Link:   export TARGET_IP=[VAST_IP] TARGET_PORT=49001 LOG_FILE=rep_49001.csv
                   nohup python3 net_probe.py > log_49001.log 2>&1 &
2. Secondary Link: export TARGET_IP=[VAST_IP] TARGET_PORT=49002 LOG_FILE=rep_49002.csv
                   nohup python3 net_probe.py > log_49002.log 2>&1 &
3. Termination:    pkill -f net_probe.py

2 watch both ports at the same time run 2 instances of the script.

49001
# export TARGET_IP=10.x.x.x TARGET_PORT=49001 LOG_FILE=vast_49001.csv
# nohup python3 net_probe.py > monitor_49001.log 2>&1 &

49002
# export TARGET_IP=10.x.x.x TARGET_PORT=49002 LOG_FILE=vast_49002.csv
# nohup python3 net_probe.py > monitor_49002.log 2>&1 &

=====================
"""

import socket
import time
import os
import sys
import csv

# Configuration from Environment Variables with defaults
TARGET_IP   = os.getenv('TARGET_IP', '127.0.0.1')
TARGET_PORT = int(os.getenv('TARGET_PORT', '22'))
INTERVAL    = float(os.getenv('INTERVAL', '1.0'))
TIMEOUT     = float(os.getenv('TIMEOUT', '2.0'))
LOG_FILE    = os.getenv('LOG_FILE', f"probe_{TARGET_PORT}.csv")

def main():
    # Write header if file is new
    write_header = not os.path.exists(LOG_FILE)
    
    print(f"Monitoring Replication: {TARGET_IP}:{TARGET_PORT}")
    print(f"Logging to: {LOG_FILE} | Interval: {INTERVAL}s")

    try:
        # buffering=1 ensures line-by-line disk commits for background safety
        with open(LOG_FILE, 'a', buffering=1, newline='') as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(['timestamp', 'status', 'latency_ms', 'error_code'])

            while True:
                ts = time.strftime('%Y-%m-%d %H:%M:%S')
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(TIMEOUT)
                
                start = time.time()
                # connect_ex is used for a non-blocking/non-exception connection attempt
                result = sock.connect_ex((TARGET_IP, TARGET_PORT))
                latency = (time.time() - start) * 1000
                sock.close()

                status = "OK" if result == 0 else "FAIL"
                
                # Write to CSV
                writer.writerow([ts, status, f"{latency:.2f}", result])
                
                # Conditional printing for cleaner nohup logs
                if result != 0:
                    print(f"[{ts}] !! ALERT !! {TARGET_PORT} DOWN | Code: {result}")
                elif latency > 100:
                    print(f"[{ts}] !! WARNING !! {TARGET_PORT} Lag: {latency:.2f}ms")
                else:
                    # Low frequency logging to keep console logs small
                    pass 
                
                time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print(f"\n[!] Monitor for port {TARGET_PORT} stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()