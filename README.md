# vastops

VAST Data **product/ops** scripts — cluster setup, VMS helpers, views/VIP pools, callhome checks, Polaris/VOC install helpers, lab shares, API probes.
Domain-specific; not general cloud tooling (`cloud-tools`) or laptop env (`system-tools`).

Expect local credentials/config outside git (e.g. `vast.creds.sh` patterns). Prefer a venv for Python helpers when needed.

Example: `create_lab_share.py` — dry-run by default; `--apply` creates wide-open multiprotocol `lab_share` (NFS/SMB/S3) using `VASTDATA_HOST` / `TF_VAR_vast_*`.
