#!/bin/bash
### Create a VIP Pool on a VAST Data Cluster
### Requires vcli installed

# Define VIP Pool parameters
NAME="protocolsPool"  # Change this as needed
CIDR="24"             # Subnet CIDR
GW="10.100.2.1"       # Gateway IP
IP_RANGE="10.100.2.201,10.100.2.206"  # VIP range
ROLE="PROTOCOLS"      # Network interface role

# Load credentials from a secure file
CRED_FILE="$HOME/vast_creds.sh"

# Check if the credentials file exists
if [[ ! -f "$CRED_FILE" ]]; then
    echo "Error: Credential file $CRED_FILE not found!" >&2
    exit 1
fi

# Source credentials
source "$CRED_FILE"

# Validate credentials
if [[ -z "$HOST" || -z "$USER" || -z "$PASS" ]]; then
    echo "Error: Failed to load credentials from $CRED_FILE" >&2
    exit 1
fi

echo "Creating VIP Pool: $NAME with range: $IP_RANGE"

# Create the VIP Pool
vcli -H "$HOST" -u "$USER" -p "$PASS" -c \
    "vippool create --name $NAME --subnet-cidr $CIDR --gw-ip $GW --ip-ranges $IP_RANGE --role $ROLE" > /dev/null

if [[ $? -ne 0 ]]; then
    echo "Error: Failed to create VIP Pool." >&2
    exit 1
fi

echo "VIP Pool $NAME created successfully!"

# Verify the VIP Pool creation
VIP_POOL_ID=$(vcli -H "$HOST" -u "$USER" -p "$PASS" -c "vippool list" 2>/dev/null | grep "$NAME" | awk '{print $2}')

if [[ -z "$VIP_POOL_ID" ]]; then
    echo "Error: VIP Pool ID retrieval failed!" >&2
    exit 1
fi

echo "VIP Pool ID: $VIP_POOL_ID"
