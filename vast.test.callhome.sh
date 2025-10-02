#!/bin/bash
# ====================================================================================
# VAST Connectivity Check Script
# File: vast_connectivity_check.sh
# Created by: Adam Tholer, VAST Data
# Purpose: Verify default route, DNS resolution, and HTTPS reachability to VAST endpoints
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ====================================================================================

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print messages
msg_success() { echo -e "${GREEN}$1${NC}"; }
msg_failure() { echo -e "${RED}$1${NC}"; }
msg_info()    { echo -e "${YELLOW}$1${NC}"; }

# Check default route
defroute=$(ip route | awk '/default/ {print $3; exit}')
echo "Node default route: $defroute"
if ping -c1 "$defroute" &>/dev/null; then
    msg_success "SUCCESS: Default route is reachable"
else
    msg_failure "FAILURE: Default route is not reachable"
fi

# List of URLs to check
urls=(
  "https://callhome.vastdata.com"
  "htt

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print messages
msg_success() { echo -e "${GREEN}$1${NC}"; }
msg_failure() { echo -e "${RED}$1${NC}"; }
msg_info()    { echo -e "${YELLOW}$1${NC}"; }

# Check default route
defroute=$(ip route | awk '/default/ {print $3; exit}')
echo "Node default route: $defroute"
if ping -c1 "$defroute" &>/dev/null; then
    msg_success "SUCCESS: Default route is reachable"
else
    msg_failure "FAILURE: Default route is not reachable"
fi

# List of URLs to check
urls=(
  "https://callhome.vastdata.com"
  "https://vast-support.s3.eu-west-1.amazonaws.com"
  "https://vast-support.s3.amazonaws.com"
  "https://vastdata-releases.s3.amazonaws.com"
  "https://vastdata-releases.s3.eu-west-1.amazonaws.com"
  "https://upload.cloud.vastdata.com"
  "https://api.cloud.vastdata.com"
  "https://www.cloud.vastdata.com"
  "https://storage.googleapis.com"
)

# Function to check each URL
check_url() {
    local url=$1
    echo ""
    echo "Checking $url"
    
    # Extract hostname
    host=$(echo "$url" | awk -F/ '{print $3}')
    
    # DNS resolution with retry
    resolved=$(getent hosts "$host" | head -n1)
    if [ -z "$resolved" ]; then
        sleep 1
        resolved=$(getent hosts "$host" | head -n1)
    fi

    if [ -n "$resolved" ]; then
        msg_success "SUCCESS: DNS resolved - $resolved"
    else
        msg_failure "FAILURE: DNS resolution failed for $host"
        return
    fi

    # TCP check for port 443
    if nc -z -w3 "$host" 443 &>/dev/null; then
        msg_success "SUCCESS: Port 443 reachable"
    else
        msg_failure "FAILURE: Port 443 not reachable"
    fi

    # HTTP status check
    status=$(curl -sI --connect-timeout 5 -o /dev/null -w "%{http_code}" "$url")
    
    case "$url:$status" in
        *callhome.vastdata.com:401) msg_success "SUCCESS: Expected HTTP 401 Unauthorized" ;;
        *vast-support.s3*:403) msg_success "SUCCESS: Expected HTTP 403 Forbidden" ;;
        *vastdata-releases.s3*:403) msg_success "SUCCESS: Expected HTTP 403 Forbidden" ;;
        *upload.cloud.vastdata.com:400) msg_success "SUCCESS: Expected HTTP 400 Bad Request" ;;
        *api.cloud.vastdata.com:404) msg_success "SUCCESS: Expected HTTP 404 Not Found" ;;
        *www.cloud.vastdata.com:200) msg_success "SUCCESS: HTTP 200 OK" ;;
        *storage.googleapis.com:400) msg_success "SUCCESS: Expected HTTP 400 Bad Request" ;;
        *:301|*:302) msg_info "INFO: HTTP $status - Redirected (usually OK)" ;;
        *:000) msg_failure "FAILURE: HTTP request failed or timed out" ;;
        *) msg_failure "FAILURE: Unexpected HTTP status $status" ;;
    esac
}

# Loop through all URLs
for url in "${urls[@]}"; do
    check_url "$url"
done
