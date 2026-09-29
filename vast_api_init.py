"""
VAST Python SDK Initialization Module
Reads existing Terraform environment variables to configure 
the official vastpy client.
"""

import os
from vastpy import VASTClient

def get_vast_client():
    """
    Initializes and returns an authenticated vastpy VASTClient using active environment variables.
    """
    # 1. Fetch the host from Native Provider Fallbacks
    vast_host = os.getenv("VASTDATA_HOST")
    if not vast_host:
        raise ValueError("Initialization Failed: 'VASTDATA_HOST' environment variable is missing.")
    
    # 2. Fetch credentials from Terraform Input Variable Overrides
    vast_user = os.getenv("TF_VAR_vast_username")
    vast_password = os.getenv("TF_VAR_vast_password")

    if not vast_user or not vast_password:
        raise ValueError("Initialization Failed: 'TF_VAR_vast_username' or 'TF_VAR_vast_password' is missing.")

    # 3. Clean up the host address (vastpy prefers just the IP or hostname without https://)
    address = vast_host.replace("https://", "").replace("http://", "")

    # 4. Initialize and return the official VAST Client connection
    return VASTClient(
        address=address,
        user=vast_user,
        password=vast_password
    )

if __name__ == "__main__":
    try:
        client = get_vast_client()
        # Light auth probe — proves credentials work against the cluster
        tenants = client.tenants.get()
        count = len(tenants) if tenants else 0
        print("✅ vastpy init + auth OK")
        print(f"   host={os.getenv('VASTDATA_HOST')}  tenants={count}")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise SystemExit(1)