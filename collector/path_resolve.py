"""Translates a host repo path stored in the DB (e.g. a Windows path like
C:\\Users\\...) into the path it's actually mounted at when this process is
running inside a container.

Two ways to configure mounts, both optional (native/host mode needs neither
— paths pass through unchanged):

- REPO_MOUNTS: JSON array of {"host": "...", "container": "..."} objects,
  for any number of separately-mounted folders. Preferred going forward —
  add a new bind mount in docker-compose.yml, add its {host, container}
  pair here, and any project under that host folder resolves correctly.
- HOST_REPOS_ROOT / CONTAINER_REPOS_ROOT: single-pair legacy form, still
  read and merged in if set (so existing setups keep working unchanged).
"""
import json
import os

REPO_MOUNTS: list[dict[str, str]] = []

_raw = os.getenv("REPO_MOUNTS")
if _raw:
    try:
        REPO_MOUNTS = json.loads(_raw)
    except (json.JSONDecodeError, TypeError):
        REPO_MOUNTS = []

_legacy_host = os.getenv("HOST_REPOS_ROOT")
_legacy_container = os.getenv("CONTAINER_REPOS_ROOT")
if _legacy_host and _legacy_container:
    REPO_MOUNTS.append({"host": _legacy_host, "container": _legacy_container})


def resolve_repo_path(stored_path: str) -> str:
    normalized_stored = stored_path.replace("\\", "/")

    for mount in REPO_MOUNTS:
        normalized_root = mount["host"].replace("\\", "/").rstrip("/")
        if normalized_stored.startswith(normalized_root):
            rest = normalized_stored[len(normalized_root):]
            return mount["container"].rstrip("/") + rest

    return stored_path
