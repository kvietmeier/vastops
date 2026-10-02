#!/usr/bin/env python3
"""
Create a VAST block subsystem (view) and one or more volumes via vastpy.

Prerequisites:
  pip install vastpy

Auth (environment — no secrets in this repo), either style:

  vastops / Terraform-style (preferred here):
    VASTDATA_HOST
    TF_VAR_vast_username
    TF_VAR_vast_password

  Or VMS_* (also accepted):
    VMS_HOST or VMS_ADDRESS  VMS hostname/IP
    VMS_USER                 username (or use VMS_TOKEN)
    VMS_PASSWORD             password
    VMS_TOKEN                optional API token (VAST 5.3+)
    VMS_TENANT_NAME          optional tenant

Does not create VIP pools or view policies — looks up an existing policy by name
(that policy must already bind the VIP pools used for NVMe/TCP paths).

Example:
  export VASTDATA_HOST=vms.example.com \\
         TF_VAR_vast_username=admin TF_VAR_vast_password=...
  python configure_vast_block.py \\
    --policy-name block-nvme-tcp \\
    --view-path /block/lab \\
    --subsystem-name lab-block \\
    --volume-name vol0 \\
    --size-gb 100 \\
    --print-connect
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _client():
    try:
        from vastpy import VASTClient
    except ImportError:
        sys.exit("vastpy is not installed. Run: pip install vastpy")

    address = (
        os.environ.get("VASTDATA_HOST")
        or os.environ.get("VMS_HOST")
        or os.environ.get("VMS_ADDRESS")
    )
    if address:
        address = address.replace("https://", "").replace("http://", "")

    token = os.environ.get("VMS_TOKEN")
    user = os.environ.get("TF_VAR_vast_username") or os.environ.get("VMS_USER")
    password = os.environ.get("TF_VAR_vast_password") or os.environ.get("VMS_PASSWORD")
    tenant = os.environ.get("VMS_TENANT_NAME")

    if not address:
        sys.exit(
            "Set VASTDATA_HOST, or VMS_HOST / VMS_ADDRESS, to the VMS hostname/IP."
        )

    kwargs: dict[str, Any] = {"address": address}
    if tenant:
        kwargs["tenant"] = tenant

    if token:
        kwargs["token"] = token
    elif user and password:
        kwargs["user"] = user
        kwargs["password"] = password
    else:
        sys.exit(
            "Set TF_VAR_vast_username + TF_VAR_vast_password, "
            "or VMS_TOKEN, or VMS_USER + VMS_PASSWORD."
        )

    return VASTClient(**kwargs)


def _first(items: list[dict], label: str) -> dict:
    if not items:
        sys.exit(f"No match for {label}.")
    return items[0]


def _find_policy(client, name: str) -> dict:
    policies = client.viewpolicies.get(name=name)
    if not isinstance(policies, list):
        policies = [policies] if policies else []
    return _first(policies, f"view policy name={name!r}")


def _find_view(client, path: str | None, name: str | None) -> dict | None:
    views = client.views.get()
    if not isinstance(views, list):
        views = [views] if views else []
    for v in views:
        if path and v.get("path") == path:
            return v
        if name and (v.get("name") == name or v.get("title") == name):
            return v
    return None


def _ensure_block_view(
    client,
    *,
    policy_id: int,
    view_path: str,
    subsystem_name: str,
) -> tuple[dict, bool]:
    existing = _find_view(client, view_path, subsystem_name)
    if existing:
        protocols = existing.get("protocols") or []
        if "BLOCK" not in protocols and protocols != ["BLOCK"]:
            print(
                f"WARNING: existing view id={existing.get('id')} path={existing.get('path')} "
                f"protocols={protocols} (expected BLOCK).",
                file=sys.stderr,
            )
        return existing, False

    view = client.views.post(
        path=view_path,
        policy_id=policy_id,
        protocols=["BLOCK"],
        name=subsystem_name,
        create_dir=True,
    )
    return view, True


def _list_volumes(client, view_id: int) -> list[dict]:
    try:
        vols = client.volumes.get(view_id=view_id)
    except Exception:
        vols = client.volumes.get()
    if not isinstance(vols, list):
        vols = [vols] if vols else []
    return [v for v in vols if v.get("view_id") == view_id or view_id in (v.get("view"),)]


def _ensure_volumes(
    client,
    *,
    view_id: int,
    volume_name: str,
    size_bytes: int,
    count: int,
) -> list[dict]:
    existing = _list_volumes(client, view_id)
    by_name = {v.get("name"): v for v in existing}
    created: list[dict] = []

    for i in range(count):
        name = volume_name if count == 1 else f"{volume_name}{i}"
        if name in by_name:
            created.append(by_name[name])
            print(f"Volume exists: name={name} id={by_name[name].get('id')}")
            continue
        vol = client.volumes.post(view_id=view_id, name=name, size=size_bytes)
        created.append(vol)
        print(f"Volume created: name={name} id={vol.get('id')} size_bytes={size_bytes}")

    return created


def _vip_ips_from_policy(client, policy: dict) -> list[str]:
    """Collect VIP addresses from pools referenced by the view policy."""
    pool_ids: list[int] = []
    for key in ("vip_pools", "vippool_ids", "vip_pool_ids", "vippools"):
        raw = policy.get(key)
        if not raw:
            continue
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, int):
                    pool_ids.append(item)
                elif isinstance(item, dict) and "id" in item:
                    pool_ids.append(int(item["id"]))
                elif isinstance(item, str) and item.isdigit():
                    pool_ids.append(int(item))
        break

    ips: list[str] = []
    pools = client.vippools.get()
    if not isinstance(pools, list):
        pools = [pools] if pools else []

    selected = pools
    if pool_ids:
        id_set = set(pool_ids)
        selected = [p for p in pools if p.get("id") in id_set]

    for pool in selected if pool_ids else []:
        for key in ("ip_ranges", "addresses", "ips", "vips"):
            raw = pool.get(key)
            if not raw:
                continue
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        ips.append(item)
                    elif isinstance(item, dict):
                        start = item.get("start_ip") or item.get("start") or item.get("ip")
                        end = item.get("end_ip") or item.get("end")
                        if start and end and start != end:
                            ips.append(f"{start}-{end}")
                        elif start:
                            ips.append(str(start))
            break
        start = pool.get("start_ip")
        end = pool.get("end_ip")
        if start:
            ips.append(f"{start}-{end}" if end and end != start else str(start))

    # De-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out


def _print_connect(vips: list[str], port: int, nqn: str | None) -> None:
    print("\n# NVMe/TCP connect hints (replace LOCAL_IP with storage NIC IPv4)")
    print("# Use the same port everywhere (discovery, connect, firewall).")
    if not vips:
        print("# (Could not resolve VIP list from policy — fill in portal IPs manually.)")
        vips = ["192.168.1.50"]

    first = vips[0].split("-")[0]
    print(f"# discovery portal: {first}:{port}  local: LOCAL_IP")
    if nqn:
        print(f"# connect NQN: {nqn}")
    print("\n# Multipath: use each portal VIP (up to 16 paths)")
    for vip in vips:
        addr = vip.split("-")[0]
        print(f"#   portal {addr}:{port}")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Create VAST BLOCK subsystem view + volumes (existing policy required)."
    )
    p.add_argument("--policy-name", required=True, help="Existing view policy name")
    p.add_argument("--view-path", required=True, help="New empty path for the block view")
    p.add_argument("--subsystem-name", required=True, help="Block subsystem name (into NQN)")
    p.add_argument("--volume-name", default="vol0", help="Volume name prefix (default: vol0)")
    p.add_argument("--size-gb", type=int, default=100, help="Volume size in GiB (default: 100)")
    p.add_argument("--volume-count", type=int, default=1, help="Number of volumes (default: 1)")
    p.add_argument("--port", type=int, default=4420, help="NVMe/TCP port (default: 4420)")
    p.add_argument(
        "--print-connect",
        action="store_true",
        help="Print NVMe/TCP discovery/connect portal hints",
    )
    args = p.parse_args()

    if args.size_gb < 1:
        sys.exit("--size-gb must be >= 1")
    if args.volume_count < 1:
        sys.exit("--volume-count must be >= 1")

    client = _client()
    policy = _find_policy(client, args.policy_name)
    print(f"Policy: name={policy.get('name')} id={policy.get('id')}")

    view, created = _ensure_block_view(
        client,
        policy_id=int(policy["id"]),
        view_path=args.view_path,
        subsystem_name=args.subsystem_name,
    )
    action = "created" if created else "reused"
    nqn = view.get("nqn") or view.get("subsystem_nqn")
    print(
        f"View {action}: id={view.get('id')} path={view.get('path')} "
        f"name={view.get('name')} nqn={nqn}"
    )

    size_bytes = args.size_gb * 1024**3
    volumes = _ensure_volumes(
        client,
        view_id=int(view["id"]),
        volume_name=args.volume_name,
        size_bytes=size_bytes,
        count=args.volume_count,
    )

    vips = _vip_ips_from_policy(client, policy)
    print(f"VIP hints from policy pools ({len(vips)}): {', '.join(vips) if vips else '(none resolved)'}")
    print(f"Volumes ready: {len(volumes)}")

    if args.print_connect:
        _print_connect(vips, args.port, nqn)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
