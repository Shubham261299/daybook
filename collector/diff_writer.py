"""Writes diff patch text to disk under DIFF_STORAGE_PATH, keyed by commit hash.

Never touches the source repo — only writes into this project's own data folder.
Skips writing (but still returns None for diff_path, metadata is unaffected)
for commits whose *entire* changed-file set matches the exclusion patterns.
"""
import fnmatch
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DIFF_STORAGE_PATH = Path(os.getenv("DIFF_STORAGE_PATH", "./data/diffs"))
if not DIFF_STORAGE_PATH.is_absolute():
    DIFF_STORAGE_PATH = (BASE_DIR / DIFF_STORAGE_PATH).resolve()

EXCLUSIONS_PATH = Path(os.getenv("DIFF_EXCLUSIONS_PATH", "./config/diff_exclusions.yaml"))
if not EXCLUSIONS_PATH.is_absolute():
    EXCLUSIONS_PATH = (BASE_DIR / EXCLUSIONS_PATH).resolve()


def _load_exclusion_patterns() -> list[str]:
    if not EXCLUSIONS_PATH.exists():
        return []
    with open(EXCLUSIONS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("exclude", [])


_PATTERNS = _load_exclusion_patterns()


def _is_excluded(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").lower()
    for pattern in _PATTERNS:
        p = pattern.replace("\\", "/").lower()
        if fnmatch.fnmatch(normalized, p) or fnmatch.fnmatch(os.path.basename(normalized), p):
            return True
    return False


def write_diff(project_slug: str, commit_hash: str, changed_files: list[str], diff_text: str) -> str | None:
    """Writes diff_text to data/diffs/<project_slug>/<hash>.patch unless every
    changed file matches an exclusion pattern, or there's no diff text at all.
    Returns the relative path (from DIFF_STORAGE_PATH) if written, else None.
    """
    if not diff_text or not diff_text.strip():
        return None

    if changed_files and all(_is_excluded(f) for f in changed_files):
        return None

    project_dir = DIFF_STORAGE_PATH / project_slug
    project_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{commit_hash}.patch"
    full_path = project_dir / filename
    full_path.write_text(diff_text, encoding="utf-8")

    return f"{project_slug}/{filename}"
