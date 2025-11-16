#!/bin/bash
defroute=$(ip route | awk '/default/ {print $3; exit}');
echo "Node default route: $defroute";
ping -c1 "$defroute" &>/dev/null && echo "SUCCESS: Default route is reachable" || echo "FAILURE: Default route is not reachable";

for url in \
  "https://callhome.vastdata.com" \
  "https://vast-support.s3.eu-west-1.amazonaws.com" \
  "https://vast-support.s3.amazonaws.com" \
  "https://vastdata-releases.s3.amazonaws.com" \
  "https://vastdata-releases.s3.eu-west-1.amazonaws.com" \
  "https://upload.cloud.vastdata.com" \
  "https://api.cloud.vastdata.com" \
  "https://www.cloud.vastdata.com" \
  "https://storage.googleapis.com"; do
  echo -e "\nChecking $url"
  host=$(echo "$url" | awk -F/ '{print $3}')
  resolved=$(getent hosts "$host" | head -n1)
  [ -n "$resolved" ] && echo "SUCCESS: DNS Resolved - $resolved" || { echo "FAILURE: DNS resolution failed for $host"; continue; }
  status=$(curl -sI --connect-timeout 5 -o /dev/null -w "%{http_code}" "$url")
  case "$url:$status" in
    *callhome.vastdata.com:401) echo "SUCCESS: Port 443 reachable. HTTP 401 Unauthorized (expected)." ;;
    *vast-support.s3*:403) echo "SUCCESS: Port 443 reachable. HTTP 403 Forbidden (expected)." ;;
    *vastdata-releases.s3*:403) echo "SUCCESS: Port 443 reachable. HTTP 403 Forbidden (expected)." ;;
    *upload.cloud.vastdata.com:400) echo "SUCCESS: Port 443 reachable. HTTP 400 Bad Request (expected)." ;;
    *api.cloud.vastdata.com:404) echo "SUCCESS: Port 443 reachable. HTTP 404 Not Found (expected)." ;;
    *www.cloud.vastdata.com:200) echo "SUCCESS: Port 443 reachable. HTTP 200 OK." ;;
    *storage.googleapis.com:400) echo "SUCCESS: Port 443 reachable. HTTP 400 Bad Request (expected)." ;;
    *:301|*:302) echo "INFO: Port 443 reachable. HTTP $status - Redirected (usually OK)." ;;
    *:000) echo "FAILURE: Port 443 not reachable or timed out. Check firewall, proxy, or SSL interception." ;;
    *) echo "FAILURE: Unexpected HTTP status: $status" ;;
  esac
done
