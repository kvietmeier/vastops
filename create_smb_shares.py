#!/usr/bin/env python3
"""
Copyright 2026 Karl V.
Licensed under the Apache License, Version 2.0 (the "License");

Provision a basic lab SMB view + policy using env vars from set_var54 / _vast_apply
(via vast_api_init.get_vast_client).

Default is dry-run (plan). Pass --apply to create.
"""

import argparse
import os
import sys

from vast_api_init import get_vast_client

POLICY_SPEC = {
    "name": "smb_policy",
    "flavor": "SMB",
    "smb_is_ca": True,
    "smb_read_write": "*",
}

VIEW_SPEC = {
    "path": "/smb_share01",
    "name": "smb_share01",
    "create_dir": True,
    "protocols": ["SMB"],
}


def _id(obj):
    return obj["id"] if isinstance(obj, dict) else obj.id


def _find_by_name(items, name):
    if not items:
        return None
    for item in items:
        if item.get("name") == name:
            return item
    return None


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Provision a basic lab SMB share (dry-run by default)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create the policy and view (default is dry-run only)",
    )
    return parser.parse_args()


def provision_windows_server_smb(apply=False):
    client = get_vast_client()
    host = os.getenv("VASTDATA_HOST")
    mode = "APPLY" if apply else "DRY-RUN"

    print(f"[{mode}] target host={host}")
    print(f"[{mode}] would create viewpolicy: {POLICY_SPEC}")
    print(f"[{mode}] would create view: {VIEW_SPEC}  (policy_id=<new or existing>)")

    existing_policy = _find_by_name(client.viewpolicies.get(), POLICY_SPEC["name"])
    existing_view = _find_by_name(client.views.get(), VIEW_SPEC["name"])

    if existing_policy:
        print(f"[{mode}] existing policy '{POLICY_SPEC['name']}' id={existing_policy.get('id')}")
    else:
        print(f"[{mode}] policy '{POLICY_SPEC['name']}' does not exist yet")

    if existing_view:
        print(f"[{mode}] existing view '{VIEW_SPEC['name']}' id={existing_view.get('id')}")
    else:
        print(f"[{mode}] view '{VIEW_SPEC['name']}' does not exist yet")

    if not apply:
        print("[DRY-RUN] no changes made — re-run with --apply to create")
        return

    if existing_policy:
        policy_id = existing_policy["id"]
        print(f"[APPLY] reusing policy_id={policy_id}")
    else:
        policy = client.viewpolicies.post(**POLICY_SPEC)
        policy_id = _id(policy)
        print(f"[APPLY] created policy_id={policy_id}")

    if existing_view:
        print(f"[APPLY] view already exists id={existing_view['id']} — skipped")
        return

    view = client.views.post(policy_id=policy_id, **VIEW_SPEC)
    view_id = _id(view)
    print(f"✅ SMB lab share created on {host}")
    print(f"   policy_id={policy_id}  view_id={view_id}  path={VIEW_SPEC['path']}")


if __name__ == "__main__":
    args = parse_arguments()
    try:
        provision_windows_server_smb(apply=args.apply)
    except Exception as e:
        print(f"❌ CRITICAL: VAST configuration failed: {e}")
        sys.exit(1)
