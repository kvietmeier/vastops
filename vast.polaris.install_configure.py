#!/usr/bin/env python3
# ============================================================================
#  VAST Data Cloud Cluster Automation Script
#
#  Author: Karl Vietmeier
#
#  Overview:
#    This script automates the end-to-end deployment of a VAST Data cluster 
#    on cloud infrastructure. It orchestrates both the infrastructure 
#    provisioning via the vastcloud CLI and the cluster configuration 
#    stages via Terraform.
#
#    Workflow:
#      1. Provision cluster infrastructure using the vastcloud CLI.
#      2. Extract VMS IP and VIP pool details from the state.
#      3. Calculate a safe DNS IP from the VIP pool and inject it as 
#         the TF_VAR_vms_host environment variable.
#      4. Poll the VAST API until the cluster reaches the ONLINE state 
#         (up to 60 minutes).
#      5. Wait an additional 3 minutes for database synchronization.
#      6. Clean and reinitialize the Terraform configuration directory.
#      7. Apply the cluster configuration using Terraform.
#      8. Extract and decrypt S3 user keys from the Terraform state using GPG.
#      9. Output a comprehensive access guide (S3, NFS, SMB) and elapsed time.
#
#  Notes:
#    - Designed to be quiet except for stage/status reporting.
#    - Polling interval is 3 minutes, max wait 60 minutes for ONLINE.
#    - Assumes vastcloud, terraform, and gpg are installed and in PATH.
#    - Requires local PGP private keys to be imported for S3 key decryption.
#
#  License:
#    Copyright (c) 2026 Karl Vietmeier
# ============================================================================

import subprocess
import time
import os
import sys
import json
import requests
import urllib3
import ipaddress
import re
from pathlib import Path

urllib3.disable_warnings()

# --- vastcloud CLI Env Vars ---
CLUSTER_NAME = os.getenv("VAST_CLUSTER_NAME", "aws-cluster01")
CLOUD_PROVIDER = os.getenv("VAST_CLOUD_PROVIDER", "aws").lower()

# --- Paths & Env Vars ---
USER = os.getenv('USER', 'root')
# Target the deep Terraform output directory dynamically
VAST_TF_DIR = os.getenv("VAST_TF_DIR", os.path.expanduser(f"~/.vast/clusters/{CLUSTER_NAME}/terraform/{CLOUD_PROVIDER}/voc"))
CONFIG_DIR = os.getenv("VAST_CONFIG_DIR", f"/home/{USER}/Terraform/vastdata/cluster_config")
TFVARS_FILE = os.getenv("VAST_TFVARS_FILE", "cluster.cfg.vars.terraform.tfvars")
OUTPUT_DIR = os.getenv("VAST_SECRETS_DIR", f"/home/{USER}/Terraform/vastdata/secrets")

# AWS Specific
AWS_SG_IDS = os.getenv("VAST_AWS_SG_IDS", "")
SUBNET = os.getenv("VAST_SUBNET", "")

# GCP Specific
GCP_PROJECT_ID = os.getenv("VAST_GCP_PROJECT_ID", "")
GCP_SA_EMAIL = os.getenv("VAST_GCP_SA_EMAIL", "")
GCP_PROTOCOL_VIPS = os.getenv("VAST_GCP_PROTOCOL_VIPS", "")
GCP_REGION = os.getenv("VAST_GCP_REGION", "")
GCP_ZONE = os.getenv("VAST_GCP_ZONE", "")

# --- Defaults ---
USERNAME = os.getenv("VAST_USERNAME", "admin")
PASSWORD = os.getenv("VAST_PASSWORD", "123456")
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

def run_vastcloud_cli():
    """Executes the vastcloud CLI for Stage 1 provisioning in non-interactive mode."""
    cmd = [
        "vastcloud", "cluster", "create",
        "--select", CLUSTER_NAME,
        "--non-interactive",
        "--skip-preflight",
        "--skip-checker"
    ]

    if CLOUD_PROVIDER == "aws":
        if AWS_SG_IDS:
            cmd.extend(["--aws-security-group-ids", AWS_SG_IDS])
        if SUBNET:
            cmd.extend(["--subnet", SUBNET])
            
    elif CLOUD_PROVIDER == "gcp":
        if GCP_PROJECT_ID:
            cmd.extend(["--gcp-project-id", GCP_PROJECT_ID])
        if GCP_SA_EMAIL:
            cmd.extend(["--gcp-service-account-email", GCP_SA_EMAIL])
        if GCP_PROTOCOL_VIPS:
            cmd.extend(["--protocol-vips", GCP_PROTOCOL_VIPS])
        if GCP_REGION:
            cmd.extend(["--region", GCP_REGION])
        if GCP_ZONE:
            cmd.extend(["--zone", GCP_ZONE])
        if SUBNET:
            cmd.extend(["--subnet", SUBNET])
    else:
        print(f"WARNING: Unknown cloud provider '{CLOUD_PROVIDER}'. Running base command only.")

    print(f"Executing: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_terraform_apply(path, extra_args=None):
    """Executes terraform apply for Stage 4 configuration."""
    args = ["terraform", "apply", "-auto-approve"]
    if extra_args:
        args.extend(extra_args)
    subprocess.run(args, cwd=path, check=True)

def get_terraform_output(path, key):
    """Extracts a specific output variable from Terraform/vastcloud state."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True
    )
    outputs = json.loads(result.stdout)
    return outputs.get(key, {}).get("value")

def get_dns_ip_from_cidr(cidr_str):
    """Calculates the .253 IP from a CIDR, or falls back to the last usable IP."""
    try:
        network = ipaddress.IPv4Network(cidr_str, strict=False)
        octets = str(network.network_address).split('.')
        candidate_ip_str = f"{octets[0]}.{octets[1]}.{octets[2]}.253"
        candidate_ip = ipaddress.IPv4Address(candidate_ip_str)
        
        if candidate_ip in network.hosts():
            return candidate_ip_str
            
        return str(list(network.hosts())[-1])
    except ValueError as e:
        print(f"ERROR: Invalid CIDR format '{cidr_str}': {e}", file=sys.stderr)
        sys.exit(1)

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

def clean_and_init_terraform(path):
    print(f"Cleaning Terraform state in {path}")
    subprocess.run(
        "find . -type d -name '.terraform' -exec rm -rf {} +",
        cwd=path,
        shell=True,
        check=True
    )
    for f in ["terraform.tfstate", "terraform.tfstate.backup"]:
        try:
            os.remove(os.path.join(path, f))
        except FileNotFoundError:
            pass

    print("Re-initializing Terraform...")
    subprocess.run(["terraform", "init", "-upgrade"], cwd=path, check=True)

def extract_s3_keys(tf_dir, output_dir):
    """Extracts and decrypts S3 keys, returning them for final output."""
    print(f"\n--- Extracting S3 Keys to {output_dir} ---")
    os.makedirs(output_dir, exist_ok=True)
    extracted_creds = []
    
    state_list = subprocess.run(
        ["terraform", "state", "list"], cwd=tf_dir, capture_output=True, text=True, check=True
    ).stdout
    
    resources = re.findall(r'(vastdata_user_key\.s3keys\["([^"]+)"\])', state_list)
    
    if not resources:
        print("No S3 user keys found in Terraform state.")
        return extracted_creds

    for resource_name, username in resources:
        state_show = subprocess.run(
            ["terraform", "state", "show", resource_name], 
            cwd=tf_dir, capture_output=True, text=True, check=True
        ).stdout
        
        access_key_match = re.search(r'access_key\s*=\s*"([^"]+)"', state_show)
        pgp_match = re.search(r'(-----BEGIN PGP MESSAGE-----.*?-----END PGP MESSAGE-----)', state_show, re.DOTALL)
        
        if not access_key_match or not pgp_match:
            continue
            
        access_key = access_key_match.group(1)
        pgp_block_clean = "\n".join([line.strip() for line in pgp_match.group(1).splitlines()])
        
        try:
            gpg_process = subprocess.run(
                ["gpg", "--decrypt"], input=pgp_block_clean, capture_output=True, text=True, check=True
            )
            secret_key = gpg_process.stdout.split()[-1]
            
            output_file = os.path.join(output_dir, f"{username}.txt")
            with open(output_file, "w") as f:
                f.write(f"Access Key: {access_key}\nSecret Key: {secret_key}\n")
            
            extracted_creds.append((username, access_key, secret_key))
            
        except subprocess.CalledProcessError:
            pass
            
    return extracted_creds

def main():
    # Stage 1: Provisioning via vastcloud CLI
    stage_start = time.time()
    print(f"--- Running vastcloud cli for cluster {CLUSTER_NAME} ---")
    run_vastcloud_cli()
    log_stage(f"✔ vastcloud provisioning completed in {elapsed_minutes(stage_start)} minutes")

    # Get VMS IP and VIP CIDR from the dynamic tf path
    if not os.path.isdir(VAST_TF_DIR):
        print(f"ERROR: Terraform directory not found: {VAST_TF_DIR}", file=sys.stderr)
        sys.exit(1)

    vms_ip = get_terraform_output(VAST_TF_DIR, "vms_ip")
    vip_cidr = get_terraform_output(VAST_TF_DIR, "vip_pool_cidr")
    
    if not vms_ip or not vip_cidr:
        print(f"ERROR: Could not get outputs from {VAST_TF_DIR}", file=sys.stderr)
        sys.exit(1)
        
    log_stage(f"Reported VMS IP: {vms_ip}")

    # Calculate DNS IP and set the environment variable
    dns_ip = get_dns_ip_from_cidr(vip_cidr)
    os.environ["TF_VAR_vms_host"] = dns_ip
    log_stage(f"Set TF_VAR_vms_host to {dns_ip} (extracted from {vip_cidr})")

    # Stage 2: Wait for ONLINE
    print(f"--- Waiting for VMS at {vms_ip} to reach ONLINE ---")
    online, wait_time = wait_for_online(vms_ip)
    if not online:
        sys.exit(1)

    # Stage 3: Post-online wait
    stage3_start = time.time()
    print(f"--- Cluster ONLINE, waiting {POST_ONLINE_WAIT//60} minutes before config apply ---")
    time.sleep(POST_ONLINE_WAIT)
    log_stage(f"✔ Waited {elapsed_minutes(stage3_start)} minutes after ONLINE")

    # Stage 4: Configuration via Terraform
    stage4_start = time.time()
    print(f"--- Running configuration terraform apply in {CONFIG_DIR} ---")
    clean_and_init_terraform(CONFIG_DIR)
    run_terraform_apply(CONFIG_DIR, ["-var-file", TFVARS_FILE])
    log_stage(f"✔ Configuration apply completed in {elapsed_minutes(stage4_start)} minutes")

    # Stage 5: Final Output Generation
    s3_credentials = extract_s3_keys(CONFIG_DIR, OUTPUT_DIR)
    vip_ips_raw = get_terraform_output(VAST_TF_DIR, "vip_pool_ips")
    
    if isinstance(vip_ips_raw, list):
        vip_ips = vip_ips_raw
    elif isinstance(vip_ips_raw, str) and vip_ips_raw:
        vip_ips = [ip.strip() for ip in vip_ips_raw.split(',')]
    else:
        vip_ips = [dns_ip] 

    mount_target_ip = vip_ips[0]
    remoteports_str = ",".join(vip_ips) 

    final_ip = get_terraform_output(CONFIG_DIR, "vms_ip") or vms_ip
    total_elapsed = elapsed_minutes(script_start)
    
    print("\n=======================================================")
    print("                 Workflow Complete")
    print("=======================================================")
    print(f"   VMS Management IP     : https://{final_ip}")
    print(f"   Total Elapsed Time    : {total_elapsed} minutes")
    print("\n-------------------------------------------------------")
    print("   HOW TO ACCESS THIS CLUSTER")
    print("-------------------------------------------------------")
    
    # --- S3 Access ---
    print("\n   [ S3 Storage ]")
    if s3_credentials:
        for user, ak, sk in s3_credentials:
            print(f"   • User: {user}")
            print(f"       export AWS_ACCESS_KEY_ID={ak}")
            print(f"       export AWS_SECRET_ACCESS_KEY={sk}")
            print(f"       aws s3 ls --endpoint-url http://{mount_target_ip} --no-verify-ssl")
    else:
        print("   • No S3 keys were extracted.")

    # --- NFS Access ---
    print("\n   [ NFS Mounts ]")
    print(f"   • Standard NFS:")
    print(f"       sudo mount -t nfs -o vers=3 {mount_target_ip}:/ /mnt/vast")
    print(f"   • VAST NFS (Multipath):")
    print(f"       sudo mount -t nfs -o vers=3,remoteports={remoteports_str} {mount_target_ip}:/ /mnt/vast")

    # --- SMB Access ---
    print("\n   [ SMB / CIFS ]")
    print(f"   • Windows / UNC Path:")
    print(f"       \\\\{mount_target_ip}\\<share_name>")
    print(f"   • Linux CIFS Mount:")
    print(f"       sudo mount -t cifs //{mount_target_ip}/<share_name> /mnt/vast -o username=<user>")
    print("=======================================================\n")

if __name__ == "__main__":
    main()