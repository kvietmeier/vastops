#!/usr/bin/env python3
"""
Copyright 2026 Karl V.
Licensed under the Apache License, Version 2.0 (the "License");
"""

from vastpy import VASTClient

def provision_windows_server_smb():
    try:
        client = VASTClient(user='admin', password='your_password', address='vast-vms-address')

        policy = client.viewpolicies.post(
            name="WindowsServer",
            flavor="SMB",
            smb_is_ca=True,
            smb_read_write="*"
        )

        client.views.post(
            path="/WindowsServer",
            name="WindowsServer",
            policy_id=policy.id,
            create_dir=True,
            protocols=["SMB"]
        )
        
    except Exception as e:
        print(f"CRITICAL: VAST configuration failed. Exception: {str(e)}")

if __name__ == "__main__":
    provision_windows_server_smb()