#!/usr/bin/env python3
"""
Test whether a VAST Cluster VMS is responding to API calls - is it online?

Created by: Casey Golliher - VAST Data Customer Success

This script is licensed under the Apache License, Version 2.0
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

usage: ./test_vast_api.py [<ip_or_hostname>] [<username>] [<password>]

Without input it will use the default user/pass and pull the IP from an entry in
/etc/hosts called "vms"

"""

import json
import requests
import urllib3
import sys

urllib3.disable_warnings()

# --- Defaults ---
DEFAULT_HOSTNAME = "vms"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "123456"

# --- Help / Usage ---
def print_usage():
    print(f"Usage: {sys.argv[0]} [<ip_or_hostname>] [<username>] [<password>]")
    print("Defaults:")
    print(f"  Hostname/IP : '{DEFAULT_HOSTNAME}' (resolved from /etc/hosts)")
    print(f"  Username    : '{DEFAULT_USERNAME}'")
    print(f"  Password    : '{DEFAULT_PASSWORD}'")

# --- Get IP from /etc/hosts ---
def get_ip_from_hosts(hostname=DEFAULT_HOSTNAME, hosts_file="/etc/hosts"):
    with open(hosts_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and line.endswith(hostname):
                return line.split()[0]
    raise Exception(f"Hostname '{hostname}' not found in {hosts_file}")

# --- Parse CLI Args ---
if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print_usage()
    sys.exit(0)

target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOSTNAME
username = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_USERNAME
password = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_PASSWORD

# Resolve IP if needed
if target.replace(".", "").isdigit():  # crude check for IP
    vms_ip = target
else:
    vms_ip = get_ip_from_hosts(target)

# --- API Call ---
base_url = f"https://{vms_ip}/api/v5"
token_url = f"{base_url}/token/"
view_url = f"{base_url}/views/"

# Step 1: Authenticate
auth_payload = {"username": username, "password": password}
auth_headers = {"Content-Type": "application/json", "Accept": "*/*"}

try:
    auth_response = requests.post(token_url, json=auth_payload, headers=auth_headers, verify=False)
    auth_response.raise_for_status()
    token = auth_response.json()['access']
except Exception as e:
    print("VMS is NOT responding:", e)
    sys.exit(1)

# Step 2: Confirm API is live
view_headers = {
    "Accept": "*/*",
    "Authorization": f"Bearer {token}"
}

try:
    view_response = requests.get(view_url, headers=view_headers, verify=False)
    view_response.raise_for_status()
    print("VMS is Responding and Online")
except Exception as e:
    print("VMS is NOT responding:", e)
    sys.exit(1)
