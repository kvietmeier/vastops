#!/usr/bin/bash
#====================================================================================================#
# Function: update_vms_ip
#
# Purpose:
#   Updates or adds the 'vms' hostname entry in the /etc/hosts file with the IP address obtained
#   from Terraform output in a specified VAST On Cloud cluster directory.
#
# Usage:
#   Source this script and call the function with an optional cluster directory name:
#     source /path/to/this_script.sh
#     update_vms_ip [cluster_name]
#
#   If no cluster_name is provided, defaults to 'cluster01'.
#
# Requirements:
#   - Must have 'terraform' CLI installed and initialized in the cluster directory.
#   - User must have sudo privileges to modify /etc/hosts (script will use sudo only for edits).
#
# Example:
#   update_vms_ip cluster02
#
# Environment:
#   Assumes HOME environment variable is set correctly and Terraform directories are under:
#   $HOME/Terraform/vast_on_cloud/5_3/1861115-h5-beta1/
#====================================================================================================#

# Use dynamic HOME environment variable
CLUSTER01="${HOME}/Terraform/vast_on_cloud/5_3/1861115-h5-beta1/cluster01"
CLUSTER02="${HOME}/Terraform/vast_on_cloud/5_3/1861115-h5-beta1/cluster02"
CLUSTER03="${HOME}/Terraform/vast_on_cloud/5_3/1861115-h5-beta1/cluster03"

function update_vms_ip() {
  read -p "Enter cluster name (default: cluster01): " CLUSTER_NAME
  CLUSTER_NAME=${CLUSTER_NAME:-cluster01}

  # Validate cluster name
  if [[ "$CLUSTER_NAME" != "cluster01" && "$CLUSTER_NAME" != "cluster02" && "$CLUSTER_NAME" != "cluster03" ]]; then
    echo "Invalid cluster name. Valid options are: cluster01, cluster02, cluster03."
    return 1  
  fi

  TF_DIR="${HOME}/Terraform/vast_on_cloud/5_3/1861115-h5-beta1/${CLUSTER_NAME}"

  # Change to the Terraform directory
  if ! cd "$TF_DIR"; then
    echo "Error: Failed to change directory to $TF_DIR"
    return 1
  fi

  # Read terraform outputs into variables
  VMS=$(terraform output -raw cluster_mgmt)
  VMSMON=$(terraform output -raw vms_monitor)
  VMSIP=$(terraform output -raw vms_ip)

  if [[ -z "$VMSIP" ]]; then
    echo "Error: Could not retrieve VMS_IP from 'terraform output'."
    return 1
  fi

  HOSTS_FILE="/etc/hosts"
  ENTRY_NAME="vms"

  # Check if an entry already exists
  if grep -qE "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\s+${ENTRY_NAME}\s*$" "$HOSTS_FILE"; then
    # Update existing entry
    sudo sed -i -E \
      "s|^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(\s+${ENTRY_NAME}\s*)$|${VMSIP}\1|" \
      "$HOSTS_FILE"
    echo ""
    echo "Updated /etc/hosts with '${ENTRY_NAME}' entry: ${VMSIP}    ${ENTRY_NAME}"
    echo ""
  else
    # Append new entry
    echo -e "${VMSIP}\t${ENTRY_NAME}" | sudo tee -a "$HOSTS_FILE" > /dev/null
  fi

  # Print terraform outputs
  echo "---------------------------------------------------------------------------------------"
  echo "Terraform outputs in $TF_DIR:"
  echo "vms    (cluster_mgmt): $VMS"
  echo "vmsmon (vms_monitor) : $VMSMON"
  echo "vmsip  (vms_ip)      : $VMSIP"
}

# Execute the function if the script is run directly
update_vms_ip
