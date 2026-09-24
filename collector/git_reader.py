"""Read-only access to a local git repo via GitPython.

Every function here only reads. Nothing in this module ever calls a
mutating GitPython method (checkout, reset, commit, add, push, pull,
fetch, etc.) and nothing writes into the target repo's working tree or
.git directory.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from git import Repo


@dataclass
class CommitRecord:
    commit_hash: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    authored_at: str   # ISO 8601
    committed_at: str  # ISO 8601
    message: str
    branch: str
    parent_hashes: str  # comma-separated
    files_changed: int
    insertions: int
    deletions: int
    git_tags: str        # comma-separated
    changed_files: list[str] = field(default_factory=list)
    diff_text: str = ""


def timedelta_from_offset(offset_seconds: int):
    from datetime import timedelta
    return timedelta(seconds=-offset_seconds)


def _current_branch(repo: Repo) -> str:
    try:
        return repo.active_branch.name
    except Exception:
        return "(detached)"


def tags_by_commit(repo: Repo) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for tag in repo.tags:
        try:
            h = tag.commit.hexsha
        except Exception:
            continue
        mapping.setdefault(h, []).append(tag.name)
    return mapping


def get_tags_for_repo(repo_path: str) -> dict[str, list[str]]:
    """Cheap standalone tag lookup — a git tag can be added to a commit long
    after that commit was collected (e.g. tagging a release after the fact),
    and collection skips reprocessing already-known commits for performance,
    so this needs to run as its own lightweight pass rather than only
    happening inside read_commits(). Read-only, same as everything else here.
    """
    repo = Repo(repo_path)
    if repo.bare:
        return {}
    return tags_by_commit(repo)


def read_commits(repo_path: str, since: str | None = None, skip_hashes: set[str] | None = None) -> list[CommitRecord]:
    """Read all commits reachable from HEAD, oldest work included.

    `since` (optional) is an ISO date string ("YYYY-MM-DD") to limit history.
    `skip_hashes` (optional) skips full stats/diff computation for commits
    already known (e.g. already collected) — that computation dominates
    runtime (~30x the cost of just listing commits), especially over a slow
    filesystem like a Docker bind mount, and collect_for_project() would
    just discard it anyway for commits it already has.
    Read-only: only iterates commits, never modifies the repo.
    """
    repo = Repo(repo_path)
    if repo.bare:
        return []

    branch = _current_branch(repo)
    tags_map = tags_by_commit(repo)

    kwargs = {}
    if since:
        kwargs["since"] = since

    records: list[CommitRecord] = []
    for commit in repo.iter_commits(**kwargs):
        if skip_hashes and commit.hexsha in skip_hashes:
            continue

        stats_total = commit.stats.total
        parent_hashes = ",".join(p.hexsha for p in commit.parents)

        try:
            if commit.parents:
                diff_index = commit.parents[0].diff(commit, create_patch=True)
            else:
                diff_index = commit.diff(
                    "4b825dc642cb6eb9a060e54bf8d69288fbee4904", create_patch=True
                )
            changed_files = [
                (d.b_path or d.a_path) for d in diff_index if (d.b_path or d.a_path)
            ]
            diff_text = "\n".join(
                d.diff.decode("utf-8", errors="replace")
                if isinstance(d.diff, bytes) else str(d.diff)
                for d in diff_index
            )
        except Exception:
            changed_files = list(commit.stats.files.keys())
            diff_text = ""

        records.append(CommitRecord(
            commit_hash=commit.hexsha,
            author_name=commit.author.name or "",
            author_email=commit.author.email or "",
            committer_name=commit.committer.name or "",
            committer_email=commit.committer.email or "",
            authored_at=datetime.fromtimestamp(
                commit.authored_date,
                tz=timezone(timedelta_from_offset(commit.author_tz_offset)),
            ).isoformat(),
            committed_at=datetime.fromtimestamp(
                commit.committed_date,
                tz=timezone(timedelta_from_offset(commit.committer_tz_offset)),
            ).isoformat(),
            message=commit.message.strip() if isinstance(commit.message, str) else commit.message.decode("utf-8", errors="replace").strip(),
            branch=branch,
            parent_hashes=parent_hashes,
            files_changed=stats_total.get("files", 0),
            insertions=stats_total.get("insertions", 0),
            deletions=stats_total.get("deletions", 0),
            git_tags=",".join(tags_map.get(commit.hexsha, [])),
            changed_files=changed_files,
            diff_text=diff_text,
        ))

    return records
