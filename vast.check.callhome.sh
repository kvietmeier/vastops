#!/bin/bash
# ====================================================================================
# Checking Access to VAST Call Home, Releases, and KMS
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
#   Summary:
#     • Performs DNS resolution for each endpoint
#     • Validates HTTPS / port 443 connectivity
#     • Confirms HTTP status matches the expected code
#     • Supports --debug / --quiet logging modes
# ====================================================================================

# Default logging
LOG_LEVEL="INFO"
LOG_FILE="vast_check.log"
QUIET_MODE=false

# Parse optional flags
for arg in "$@"; do
    case "$arg" in
        --debug)
            LOG_LEVEL="DEBUG"
            ;;
        --quiet)
            QUIET_MODE=true
            ;;
    esac
done

log() {
    local level="$1"
    local message="$2"

    # If quiet mode, log everything to file only
    if [ "$QUIET_MODE" = true ]; then
        echo "[$level] $message" >> "$LOG_FILE"
    else
        case "$LOG_LEVEL" in
            DEBUG)
                echo "[DEBUG] $message"
                ;;
            INFO)
                [[ "$level" != "DEBUG" ]] && echo "[INFO] $message"
                ;;
        esac
    fi
}

# Clear previous log file if quiet mode
$QUIET_MODE && > "$LOG_FILE"

# List of endpoints with expected HTTP status
ENDPOINTS=(
    "https://callhome.vastdata.com 401"
    "https://vast-support.s3.eu-west-1.amazonaws.com 403"
    "https://vast-support.s3.amazonaws.com 403"
    "https://vastdata-releases.s3.amazonaws.com 403"
    "https://vastdata-releases.s3.eu-west-1.amazonaws.com 403"
    "https://upload.cloud.vastdata.com 400"
    "https://api.cloud.vastdata.com 404"
    "https://www.cloud.vastdata.com 200"
)

log INFO "=== Checking Access to VAST Call Home, Releases, and KMS ==="

for entry in "${ENDPOINTS[@]}"; do
    url=$(echo "$entry" | awk '{print $1}')
    expected=$(echo "$entry" | awk '{print $2}')
    host=$(echo "$url" | awk -F/ '{print $3}')

    log INFO ""
    log INFO "Checking: $url"

    # DNS resolution
    resolved=$(getent hosts "$host" | head -n1)
    if [ -n "$resolved" ]; then
        log INFO "DNS resolved: $resolved"
    else
        log INFO "DNS resolution failed for $host"
        continue
    fi

    # HTTPS check
    status=$(curl -sI --connect-timeout 5 -o /dev/null -w "%{http_code}" "$url")
    case "$status" in
        "$expected")
            log INFO "HTTPS reachable: expected HTTP $expected"
            ;;
        301|302)
            log INFO "HTTPS reachable: HTTP $status Redirect (usually OK)"
            ;;
        000)
            log INFO "HTTPS not reachable or timed out"
            ;;
        *)
            log INFO "HTTPS returned unexpected status: $status (expected $expected)"
            ;;
    esac
done

log INFO ""
log INFO "=== Test Complete ==="
log INFO ""

$QUIET_MODE && echo "Output logged to $LOG_FILE"
