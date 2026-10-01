#!/usr/bin/env python3
"""
Print VAST cluster / VMS version info via vastpy (quick validation helper).

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

Example:
  export VASTDATA_HOST=vms.example.com \\
         TF_VAR_vast_username=admin TF_VAR_vast_password=...
  python get_vast_versions.py
"""

from __future__ import annotations

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


def _as_list(obj: Any) -> list:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    return [obj]


def _pick(d: dict, *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def main() -> None:
    client = _client()

    print("=== Clusters ===")
    try:
        clusters = _as_list(
            client.clusters.get(fields="name,state,build,sw_version,version,cluster_type")
        )
    except Exception:
        # Older / narrower schemas: name+state+build is enough for the KB matrix
        clusters = _as_list(client.clusters.get(fields="name,state,build"))

    if not clusters:
        print("(no clusters returned)")
    else:
        for c in clusters:
            if not isinstance(c, dict):
                print(c)
                continue
            name = _pick(c, "name") or "?"
            state = _pick(c, "state") or "?"
            build = _pick(c, "build", "sw_version", "version") or "?"
            ctype = _pick(c, "cluster_type")
            line = f"  name={name}  state={state}  build={build}"
            if ctype:
                line += f"  type={ctype}"
            print(line)

    # Optional: versions collection when present on this VMS
    print("\n=== Versions (if available) ===")
    try:
        versions = _as_list(client.versions.get())
        if not versions:
            print("(empty)")
        else:
            for v in versions:
                if isinstance(v, dict):
                    name = _pick(v, "name", "component", "id") or "item"
                    ver = _pick(v, "version", "build", "sw_version", "value") or v
                    print(f"  {name}: {ver}")
                else:
                    print(f"  {v}")
    except Exception as exc:
        print(f"(versions endpoint not available: {exc})")

    # One-line hint matching vastpy-cli used in lab docs
    print(
        "\n# Equivalent CLI:\n"
        "#   vastpy-cli get clusters fields=name,state,build"
    )


if __name__ == "__main__":
    main()
