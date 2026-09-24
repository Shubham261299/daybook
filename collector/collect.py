"""Collection entrypoint: for each active project, read commits (read-only)
and append any not already in the DB. Cheap, no LLM involved — safe to run
frequently.

Usage:
    python -m collector.collect            # all active projects
    python -m collector.collect --project 3
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection
from collector.git_reader import read_commits, get_tags_for_repo
from collector.diff_writer import write_diff
from collector.path_resolve import resolve_repo_path


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "project"


def _sync_tags(conn, project_id: int, project_path: str) -> int:
    """A git tag can be added to a commit well after that commit was
    collected (e.g. tagging a release after the fact) — the skip_hashes
    optimization above means read_commits() never revisits it, so tags on
    already-known commits go stale unless refreshed separately here. Cheap:
    one `repo.tags` scan, not the stats/diff work being skipped.
    """
    try:
        current_tags = get_tags_for_repo(project_path)
    except Exception:
        return 0

    rows = conn.execute(
        "SELECT commit_hash, git_tags FROM commits WHERE project_id = ?", (project_id,)
    ).fetchall()

    updated = 0
    for row in rows:
        fresh = ",".join(current_tags.get(row["commit_hash"], []))
        if fresh != (row["git_tags"] or ""):
            conn.execute(
                "UPDATE commits SET git_tags = ? WHERE project_id = ? AND commit_hash = ?",
                (fresh, project_id, row["commit_hash"]),
            )
            updated += 1

    if updated:
        conn.commit()
    return updated


def collect_for_project(conn, project_row) -> int:
    project_id = project_row["id"]
    project_path = resolve_repo_path(project_row["path"])
    project_slug = _slug(project_row["name"])

    if not Path(project_path).exists():
        print(f"  [skip] path does not exist: {project_path}")
        return 0

    existing = {
        r["commit_hash"]
        for r in conn.execute(
            "SELECT commit_hash FROM commits WHERE project_id = ?", (project_id,)
        ).fetchall()
    }

    try:
        commits = read_commits(project_path, skip_hashes=existing)
    except Exception as e:
        print(f"  [error] could not read repo at {project_path}: {e}")
        return 0

    new_count = 0
    for c in commits:
        if c.commit_hash in existing:
            continue

        diff_path = write_diff(project_slug, c.commit_hash, c.changed_files, c.diff_text)

        conn.execute(
            """
            INSERT INTO commits (
                project_id, commit_hash, author_name, author_email,
                committer_name, committer_email, authored_at, committed_at,
                message, branch, parent_hashes, files_changed, insertions,
                deletions, diff_path, git_tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, c.commit_hash, c.author_name, c.author_email,
                c.committer_name, c.committer_email, c.authored_at, c.committed_at,
                c.message, c.branch, c.parent_hashes, c.files_changed, c.insertions,
                c.deletions, diff_path, c.git_tags,
            ),
        )
        new_count += 1

    conn.commit()

    tag_updates = _sync_tags(conn, project_id, project_path)
    if tag_updates:
        print(f"  -> {tag_updates} commit(s) had tag changes synced")

    return new_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=int, help="Only collect for this project id")
    args = parser.parse_args()

    conn = get_connection()
    try:
        if args.project:
            rows = conn.execute(
                "SELECT * FROM projects WHERE id = ? AND status = 'active'", (args.project,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects WHERE status = 'active'"
            ).fetchall()

        if not rows:
            print("No active projects found.")
            return

        total_new = 0
        for row in rows:
            print(f"Collecting: {row['name']} ({row['path']})")
            new_count = collect_for_project(conn, row)
            print(f"  -> {new_count} new commit(s)")
            total_new += new_count

        print(f"\nDone. {total_new} new commit(s) across {len(rows)} project(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
