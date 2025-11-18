#!/bin/bash
###=====================================================================###
###
### VAST on Cloud XLister Cluster Setup Script
###
### Created By: Karl Vitemeier, Cloud Solutions Architect - VAST Data
###
### Functions:
###   - Load VAST credentials
###   - Add a mandatory user to the Default Tenant
###   - Create NFS Views
###   - Create S3 Views (buckets) with owner
###
### Requirements:
###   - VAST credentials file ($HOME/vast_creds)
###   - vcli available in PATH
###=====================================================================###

###============================= Variables =============================###
# Credentials
CRED_FILE="$HOME/vast_creds"

# Default pools/policies (always exist in VoC Cluster)
VIP_POOL_NAME="protocolsPool"
DEF_NFS_POLICY="NFS_policy"  # Replace with actual default NFS policy ID or name
DEF_S3_POLICY="S3_policy"    # Replace with actual default S3 policy ID or name

# Views/Buckets
NFS_PATH_BASE="nfs"
NUM_NFS_VIEWS=3
S3_BUCKET_BASE="bucket"
NUM_S3_BUCKETS=2

# Default Tenant ID
DEFAULT_TENANT_ID=1

# Mandatory user to create
NEW_USER="s3user01"
NEW_USER_PASS=""  # Leave empty to auto-generate
###=====================================================================###

###============================= Functions =============================###

# Load credentials from file
load_credentials() {
    if [[ ! -f "$CRED_FILE" ]]; then
        echo "Error: Credential file $CRED_FILE not found!" >&2
        exit 1
    fi
    source "$CRED_FILE"

    if [[ -z "$HOST" || -z "$USER" || -z "$PASS" ]]; then
        echo "Error: Failed to load credentials from $CRED_FILE" >&2
        exit 1
    fi
}

# Add user to Default Tenant
add_vast_user() {
    local USERNAME="$1"
    local PASSWORD="$2"

    if [[ -z "$USERNAME" ]]; then
        echo "Error: Username must be provided." >&2
        return 1
    fi

    # Generate a random password if not provided
    if [[ -z "$PASSWORD" ]]; then
        PASSWORD=$(openssl rand -base64 16)
        echo "Generated password for user '$USERNAME': $PASSWORD"
    fi

    echo "Creating user '$USERNAME' in Default Tenant (ID=$DEFAULT_TENANT_ID)..."
    vcli -H "$HOST" -u "$USER" -p "$PASS" -c \
        "user create --name $USERNAME --tenant-id $DEFAULT_TENANT_ID --password $PASSWORD" > /dev/null || {
        echo "Error: Failed to create user '$USERNAME'." >&2
        exit 1
    }

    # Return the user ID for S3 ownership
    USER_ID=$(vcli -H "$HOST" -u "$USER" -p "$PASS" -c "user list" \
        | awk -v name="$USERNAME" '$1==name {print $2}')
    echo "User '$USERNAME' created successfully with ID: $USER_ID"
    echo "$USER_ID"
}

# Create NFS Views
create_nfs_views() {
    local POLICY_ID="$1" PATH_BASE="$2" NUM_VIEWS="$3"
    for ((i=1; i<=NUM_VIEWS; i++)); do
        local VIEW_PATH="/${PATH_BASE}${i}"
        echo "Creating NFS view: $VIEW_PATH"
        vcli -H "$HOST" -u "$USER" -p "$PASS" -c \
            "view create --path $VIEW_PATH --protocols NFS --policy-id $POLICY_ID --create-dir" > /dev/null || {
            echo "Error: Failed to create NFS view $VIEW_PATH" >&2
            exit 1
        }
    done
    echo "NFS views created successfully."
}

# Create S3 Buckets (views) owned by a user
create_s3_views() {
    local POLICY_ID="$1" BUCKET_BASE="$2" NUM_BUCKETS="$3" OWNER_ID="$4"
    for ((i=1; i<=NUM_BUCKETS; i++)); do
        local BUCKET_NAME="${BUCKET_BASE}${i}"
        echo "Creating S3 bucket: $BUCKET_NAME (owner ID: $OWNER_ID)"
        vcli -H "$HOST" -u "$USER" -p "$PASS" -c \
            "view create --path /$BUCKET_NAME --protocols S3 --policy-id $POLICY_ID --owner $OWNER_ID --s3-bucket" > /dev/null || {
            echo "Error: Failed to create S3 bucket $BUCKET_NAME" >&2
            exit 1
        }
    done
    echo "S3 buckets created successfully."
}

###=====================================================================###
###--- Main Execution
###=====================================================================###
main() {
    load_credentials

    # Get the existing protocols pool ID
    VIP_POOL_ID=$(vcli -H "$HOST" -u "$USER" -p "$PASS" -c "vippool list" \
        | awk -v pool="$VIP_POOL_NAME" '$1==pool {print $2}')
    if [[ -z "$VIP_POOL_ID" ]]; then
        echo "Error: Protocols VIP Pool '$VIP_POOL_NAME' not found!" >&2
        exit 1
    fi
    echo "Using VIP Pool '$VIP_POOL_NAME' with ID: $VIP_POOL_ID"

    # Use existing default policies
    NFS_POLICY_ID="$DEF_NFS_POLICY"
    S3_POLICY_ID="$DEF_S3_POLICY"
    echo "Using NFS Policy ID: $NFS_POLICY_ID"
    echo "Using S3 Policy ID: $S3_POLICY_ID"

    # Create mandatory user (owner of S3 buckets)
    USER_ID=$(add_vast_user "$NEW_USER" "$NEW_USER_PASS")

    # Create NFS views
    create_nfs_views "$NFS_POLICY_ID" "$NFS_PATH_BASE" "$NUM_NFS_VIEWS"

    # Create S3 buckets with the new user as owner
    create_s3_views "$S3_POLICY_ID" "$S3_BUCKET_BASE" "$NUM_S3_BUCKETS" "$USER_ID"

    echo "VAST on Cloud XLister setup complete!"
}

main "$@"
