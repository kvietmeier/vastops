#!/usr/bin/env python3
# ============================================================================
#  VAST Data Cloud Cluster Automation Script
#
#  Author: Karl Vietmeier
#
#  Overview:
#    This script automates the end-to-end deployment of a VAST Data cluster 
#    on cloud infrastructure using Terraform. It orchestrates both the 
#    infrastructure provisioning and the cluster configuration stages.
#
#    Workflow:
#      1. Run the first Terraform apply to create cluster infrastructure.
#      2. Extract the VMS IP address from Terraform output.
#      3. Update /etc/hosts with the VMS entry.
#      4. Poll the VAST API until the cluster reaches the ONLINE state 
#         (up to 60 minutes).
#      5. Wait an additional 5 minutes for database synchronization.
#      6. Clean and reinitialize the configuration directory.
#      7. Run the second Terraform apply using a non-standard tfvars file.
#      8. Report VMS IP and total elapsed time.
#
#  Notes:
#    - Designed to be quiet except for stage/status reporting.
#    - Polling interval is 3 minutes, max wait 60 minutes for ONLINE.
#    - Requires sudo access to update /etc/hosts.
#    - Assumes Terraform and curl are installed and in PATH.
#
#  License:
#    Copyright (c) 2025 Karl Vietmeier
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
# ============================================================================

import subprocess
import time
import os
import sys
import json
import requests
import urllib3
from pathlib import Path

urllib3.disable_warnings()

# --- Paths ---
# Adjust these paths as needed for your environment
CLUSTER_DIR = f"/home/{os.getenv('USER')}/Terraform/vast_on_cloud/5_3/1861115-h5-beta1/cluster01"
CONFIG_DIR = f"/home/{os.getenv('USER')}/Terraform/vastdata/cluster_config"
TFVARS_FILE = "cluster.cfg.vars.terraform.tfvars"

# --- Defaults ---
USERNAME = "admin"
PASSWORD = "123456"
CHECK_INTERVAL = 180    # 3 minutes
MAX_WAIT = 60 * 60      # 60 minutes
POST_ONLINE_WAIT = 180  # 3 minutes

# --- Helpers ---
script_start = time.time()

def elapsed_minutes(start_time):
    return round((time.time() - start_time) / 60, 1)

def log_stage(msg, start_time=None):
    if start_time:
        print(f"[+{elapsed_minutes(start_time)}m] {msg}", flush=True)
    else:
        print(msg, flush=True)

def run_terraform_apply(path, extra_args=None):
    args = ["terraform", "apply", "-auto-approve"]
    if extra_args:
        args.extend(extra_args)
    subprocess.run(args, cwd=path, check=True)

def get_terraform_output(path, key):
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True
    )
    outputs = json.loads(result.stdout)
    return outputs.get(key, {}).get("value")

# --- Update /etc/hosts ---
def update_hosts(ip):
    hostname = "vms"
    new_line = f"{ip}\t{hostname}\n"

    try:
        with open("/etc/hosts", "r") as f:
            lines = f.readlines()

        found = False
        for i, line in enumerate(lines):
            if line.strip().endswith(hostname):
                lines[i] = new_line
                found = True
                break
        if not found:
            lines.append(new_line)

        # Write changes with sudo
        subprocess.run(
            ["sudo", "tee", "/etc/hosts"],
            input="".join(lines),
            text=True,
            capture_output=True,
            check=True
        )
        print(f"/etc/hosts updated: {ip} {hostname}")

    except Exception as e:
        print(f"Error updating /etc/hosts: {e}", file=sys.stderr)
        sys.exit(1)

# --- VMS API ---
def get_vms_state(ip, username=USERNAME, password=PASSWORD):
    base_url = f"https://{ip}/api/v5"
    token_url = f"{base_url}/token/"
    cluster_url = f"{base_url}/clusters/"
    try:
        auth_resp = requests.post(
            token_url,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=(3,5)
        )
        auth_resp.raise_for_status()
        token = auth_resp.json()['access']
    except Exception:
        return "OFFLINE"

    try:
        cluster_resp = requests.get(
            cluster_url,
            headers={"Authorization": f"Bearer {token}"},
            verify=False,
            timeout=(3,5)
        )
        cluster_resp.raise_for_status()
        clusters = cluster_resp.json()
        if clusters and isinstance(clusters, list):
            return clusters[0].get("state", "UNKNOWN")
        return "UNKNOWN"
    except Exception:
        return "OFFLINE"

# --- Poll until ONLINE ---
def wait_for_online(ip, username=USERNAME, password=PASSWORD):
    start_time = time.time()
    deadline = start_time + MAX_WAIT
    last_state = None
    state_start = start_time

    while time.time() < deadline:
        state = get_vms_state(ip, username, password)

        if state != last_state:
            duration = round((time.time() - state_start)/60,1)
            if last_state is None:
                log_stage(f"VMS state: {state}", start_time)
            else:
                log_stage(f"Transition: {last_state} → {state} ({duration} min)", start_time)
            last_state = state
            state_start = time.time()

        if state == "ONLINE":
            total = elapsed_minutes(start_time)
            log_stage(f"✔ VMS reached ONLINE in {total} minutes", start_time)
            return True, total

        log_stage(f"VMS not ready yet (state={state}), waiting...", start_time)
        time.sleep(CHECK_INTERVAL)

    log_stage("ERROR: VMS did not reach ONLINE within max wait", start_time)
    return False, elapsed_minutes(start_time)

# --- Clean and re-init Terraform ---
def clean_and_init_terraform(path):
    print(f"Cleaning Terraform state in {path}")
    # Remove .terraform directories
    subprocess.run(
        "find . -type d -name '.terraform' -exec rm -rf {} +",
        cwd=path,
        shell=True,
        check=True
    )
    # Remove state files
    for f in ["terraform.tfstate", "terraform.tfstate.backup"]:
        try:
            os.remove(os.path.join(path, f))
        except FileNotFoundError:
            pass

    # Re-initialize terraform
    print("Re-initializing Terraform...")
    subprocess.run(["terraform", "init", "-upgrade"], cwd=path, check=True)



# --- Workflow ---
def main():
    # Stage 1: First Terraform apply
    stage_start = time.time()
    print(f"--- Running first terraform apply in {CLUSTER_DIR} ---")
    run_terraform_apply(CLUSTER_DIR)
    log_stage(f"✔ First terraform apply completed in {elapsed_minutes(stage_start)} minutes")

    # Get VMS IP from Terraform
    vms_ip = get_terraform_output(CLUSTER_DIR, "vms_ip")
    if not vms_ip:
        print("ERROR: Could not get vms_ip from Terraform output", file=sys.stderr)
        sys.exit(1)
    log_stage(f"Terraform reported VMS IP: {vms_ip}")

    # Update /etc/hosts immediately
    update_hosts(vms_ip)

    # Stage 2: Wait for ONLINE
    print(f"--- Waiting for VMS at {vms_ip} to reach ONLINE (max {MAX_WAIT//60} min) ---")
    online, wait_time = wait_for_online(vms_ip)
    if not online:
        sys.exit(1)

    # Stage 3: Wait 5 minutes after ONLINE
    stage3_start = time.time()
    print(f"--- Cluster ONLINE, waiting {POST_ONLINE_WAIT//60} minutes before second apply ---")
    time.sleep(POST_ONLINE_WAIT)
    log_stage(f"✔ Waited {elapsed_minutes(stage3_start)} minutes after ONLINE")

    # Stage 4: Second Terraform apply
    stage4_start = time.time()
    print(f"--- Running second terraform apply in {CONFIG_DIR} ---")
    clean_and_init_terraform(CONFIG_DIR)
    run_terraform_apply(CONFIG_DIR, ["-var-file", TFVARS_FILE])
    log_stage(f"✔ Second terraform apply completed in {elapsed_minutes(stage4_start)} minutes")

    # Final output
    final_ip = get_terraform_output(CONFIG_DIR, "vms_ip") or vms_ip
    total_elapsed = elapsed_minutes(script_start)
    print("\n=======================================================")
    print("                 Workflow complete")
    print("-------------------------------------------------------")
    print(f"   VMS IP Address        : {final_ip}")
    print(f"   Total Elapsed Time    : {total_elapsed} minutes")
    print("-------------------------------------------------------")
    print("   Next Steps:")
    print("     • Run the alias `pgpsecrets` to retrieve user keys for S3")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
