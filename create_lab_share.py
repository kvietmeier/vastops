#!/usr/bin/env python3
"""
Provision a wide-open multiprotocol lab share (NFS + SMB + S3).

Uses VASTDATA_HOST / TF_VAR_vast_username / TF_VAR_vast_password via vast_api_init.
Default is dry-run. Pass --apply to create. Pass --quiet to suppress plan/compare noise.

WARNING: Lab-only policy (RW "*"). Do not use this in customer production environments as-is.
"""

import argparse
import os
import sys

from vast_api_init import get_vast_client

POLICY_NAME = "lab_policy"
VIEW_PATH = "/lab_share"
SHARE_NAME = "lab_share"
# S3 bucket names: lowercase, numbers, periods, hyphens only (no underscores)
BUCKET_NAME = "lab-share"

POLICY_SPEC = {
    "name": POLICY_NAME,
    "flavor": "NFS",
    "auth_source": "RPC_AND_PROVIDERS",
    "allowed_characters": "LCD",
    "path_length": "LCD",
    "gid_inheritance": "LINUX",
    "nfs_read_write": ["*"],
    "nfs_no_squash": ["*"],
    "nfs_root_squash": [],
    "smb_read_write": ["*"],
    "s3_read_write": ["*"],
    "smb_file_mode": 666,
    "smb_directory_mode": 777,
    "enable_access_to_snapshot_dir_in_subdirs": True,
}

# Lab vs hardened multiprotocol guidance (dry-run comparison only).
POLICY_BEST_PRACTICE = [
    ("flavor", "NFS", "NFS flavor for a single NFS+SMB+S3 namespace", "ok"),
    (
        "auth_source",
        "RPC_AND_PROVIDERS",
        "NFS UID/GID via RPC; SMB/S3 can use identity providers",
        "ok",
    ),
    (
        "allowed_characters / path_length",
        "LCD / LCD",
        "LCD is the usual Windows/cross-protocol choice",
        "ok",
    ),
    ("gid_inheritance", "LINUX", "LINUX is typical for Linux NFS clients", "ok"),
    (
        "nfs/smb/s3_read_write",
        '["*"]',
        "Prefer lab/client CIDRs or principals in non-lab use",
        "lab-only",
    ),
    (
        "nfs_no_squash",
        '["*"]',
        "Prefer empty or tight CIDRs; root stays un-squashed for everyone",
        "lab-only",
    ),
    (
        "nfs_root_squash",
        "[]",
        "Empty + no_squash * means no effective root squash",
        "lab-only",
    ),
    (
        "smb_file_mode / smb_directory_mode",
        "666 / 777",
        "Hardened defaults are closer to 644 / 755",
        "lab-only",
    ),
    (
        "vip_pools / vippool_permissions",
        "(unset)",
        "Production usually binds policy RW to PROTOCOLS VIP pool(s)",
        "gap",
    ),
    (
        "protocols_audit / data_* logging",
        "(unset)",
        "Enable audit when the share holds anything beyond throwaway lab data",
        "gap",
    ),
    (
        "scope",
        "one multiprotocol view",
        "OK for a dump share; baselines often use per-protocol policies",
        "lab-only",
    ),
]


def _id(obj):
    return obj["id"] if isinstance(obj, dict) else obj.id


def _find_by_name(items, name):
    if not items:
        return None
    for item in items:
        if item.get("name") == name:
            return item
    return None


def _find_view(items, path=None, name=None):
    if not items:
        return None
    for item in items:
        if path and item.get("path") == path:
            return item
        if name and item.get("name") == name:
            return item
        if name and item.get("share") == name:
            return item
    return None


def _log(quiet, msg):
    if not quiet:
        print(msg)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Provision multiprotocol lab_share (NFS/SMB/S3); dry-run by default"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create the policy and view (default is dry-run only)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (skip plan dump and best-practice compare)",
    )
    parser.add_argument(
        "--bucket-owner",
        default=os.getenv("VAST_BUCKET_OWNER") or os.getenv("TF_VAR_vast_username"),
        help="S3 bucket owner username (default: VAST_BUCKET_OWNER or TF_VAR_vast_username)",
    )
    return parser.parse_args()


def print_policy_best_practice_compare():
    print("\n[COMPARE] lab_policy vs hardened multiprotocol guidance")
    print(f"{'verdict':<10} {'setting':<40} {'lab value':<22} guidance")
    print("-" * 100)
    for setting, lab_value, guidance, verdict in POLICY_BEST_PRACTICE:
        print(f"{verdict:<10} {setting:<40} {lab_value:<22} {guidance}")
    print(
        "\n[COMPARE] summary: structural multiprotocol choices look sound; "
        "RW/no-squash/modes are intentionally lab-open; VIP bind + audit are unset."
    )


def check_smb_ad_ready(client):
    """
    SMB on a view requires the tenant to have an AD provider allowed for SMB.
    Returns (ok: bool, detail: str).
    """
    try:
        ads = client.activedirectory.get()
    except Exception as e:
        return False, f"could not query Active Directory providers: {e}"

    if not ads:
        return (
            False,
            "no Active Directory provider on this cluster; "
            "SMB views need a tenant AD provider with SMB allowed",
        )

    if isinstance(ads, dict):
        ads = [ads]

    for ad in ads:
        smb_ok = ad.get("smb_allowed") in (True, "true", "True", 1)
        enabled = ad.get("enabled") in (True, "true", "True", 1)
        if smb_ok and enabled:
            domain = ad.get("domain_name") or ad.get("id")
            return True, f"AD ready for SMB (domain={domain})"

    return (
        False,
        "Active Directory exists but none are enabled with smb_allowed; "
        "join/enable AD for SMB before creating an SMB view",
    )


def provision_lab_share(apply=False, bucket_owner=None, quiet=False):
    if not bucket_owner:
        raise ValueError(
            "bucket owner required: pass --bucket-owner or set VAST_BUCKET_OWNER / TF_VAR_vast_username"
        )

    client = get_vast_client()
    host = os.getenv("VASTDATA_HOST")
    mode = "APPLY" if apply else "DRY-RUN"

    view_spec = {
        "path": VIEW_PATH,
        "create_dir": True,
        "protocols": ["NFS", "SMB", "S3"],
        "share": SHARE_NAME,
        "bucket": BUCKET_NAME,
        "bucket_owner": bucket_owner,
    }

    # Preflight before any create — SMB will 400 without AD.
    ad_ok, ad_detail = check_smb_ad_ready(client)

    _log(quiet, f"[{mode}] target host={host}")
    _log(quiet, f"[{mode}] would create viewpolicy: {POLICY_SPEC}")
    _log(quiet, f"[{mode}] would create view: {view_spec}  (policy_id=<new or existing>)")
    _log(quiet, f"[{mode}] preflight SMB/AD: {ad_detail}")
    if not quiet:
        print_policy_best_practice_compare()

    existing_policy = _find_by_name(client.viewpolicies.get(), POLICY_NAME)
    existing_view = _find_view(client.views.get(), path=VIEW_PATH, name=SHARE_NAME)

    if existing_policy:
        _log(quiet, f"\n[{mode}] existing policy '{POLICY_NAME}' id={existing_policy.get('id')}")
    else:
        _log(quiet, f"\n[{mode}] policy '{POLICY_NAME}' does not exist yet")

    if existing_view:
        _log(
            quiet,
            f"[{mode}] existing view path={existing_view.get('path')} "
            f"id={existing_view.get('id')} protocols={existing_view.get('protocols')}",
        )
    else:
        _log(quiet, f"[{mode}] view '{VIEW_PATH}' does not exist yet")

    if not apply:
        if not ad_ok:
            print(f"[DRY-RUN] BLOCKED for --apply until AD/SMB ready: {ad_detail}")
        print("[DRY-RUN] no changes made — re-run with --apply to create")
        return

    if not ad_ok and not existing_view:
        raise RuntimeError(
            f"refusing to create: {ad_detail}. "
            f"Policy may already exist (id={existing_policy.get('id') if existing_policy else 'none'}); "
            "join AD for SMB, then re-run --apply."
        )

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

    try:
        view = client.views.post(policy_id=policy_id, **view_spec)
    except Exception:
        print(
            f"[APPLY] view create failed after policy_id={policy_id} "
            f"(policy left in place; fix AD/SMB then re-run --apply)"
        )
        raise

    view_id = _id(view)
    print(f"✅ lab_share created on {host}")
    print(
        f"   policy_id={policy_id}  view_id={view_id}  "
        f"path={VIEW_PATH}  protocols=NFS,SMB,S3  bucket_owner={bucket_owner}"
    )


if __name__ == "__main__":
    args = parse_arguments()
    try:
        provision_lab_share(
            apply=args.apply, bucket_owner=args.bucket_owner, quiet=args.quiet
        )
    except Exception as e:
        print(f"❌ CRITICAL: VAST configuration failed: {e}")
        sys.exit(1)
