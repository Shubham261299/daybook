import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.backend.deps import get_db
from collector.path_resolve import resolve_repo_path

router = APIRouter()

QUIET_THRESHOLD_DAYS = int(os.getenv("QUIET_THRESHOLD_DAYS", "7"))


def _path_exists(stored_path: str) -> bool:
    return Path(resolve_repo_path(stored_path)).exists()


def _with_quiet_flag(row: dict) -> dict:
    last = row.get("last_commit_date")
    if row["status"] != "active":
        row["days_since_last_commit"] = None
        row["is_quiet"] = False
        return row
    if not last:
        row["days_since_last_commit"] = None
        row["is_quiet"] = True  # active project with zero commits ever
        return row
    days = (date.today() - datetime.fromisoformat(last).date()).days
    row["days_since_last_commit"] = days
    row["is_quiet"] = days >= QUIET_THRESHOLD_DAYS
    return row


class ProjectIn(BaseModel):
    name: str
    path: str
    status: str = "active"
    tags: str | None = None
    phase: str | None = None
    department: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    status: str | None = None
    tags: str | None = None
    phase: str | None = None
    department: str | None = None


@router.get("")
def list_projects(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        """
        SELECT p.*, MAX(date(c.authored_at)) AS last_commit_date
        FROM projects p
        LEFT JOIN commits c ON c.project_id = p.id
        GROUP BY p.id
        ORDER BY p.name
        """
    ).fetchall()
    return [_with_quiet_flag(dict(r)) for r in rows]


@router.post("")
def create_project(project: ProjectIn, conn: sqlite3.Connection = Depends(get_db)):
    if project.status not in ("active", "paused"):
        raise HTTPException(400, "status must be 'active' or 'paused'")
    if not _path_exists(project.path):
        raise HTTPException(
            400,
            f"path does not exist: {project.path} — if this is running in Docker, "
            "the folder needs to be bind-mounted (see REPO_MOUNTS in docker-compose.yml)",
        )
    try:
        cur = conn.execute(
            "INSERT INTO projects (name, path, status, tags, phase, department) VALUES (?, ?, ?, ?, ?, ?)",
            (project.name, project.path, project.status, project.tags, project.phase, project.department),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "a project with this path already exists")
    return {"id": cur.lastrowid}


@router.patch("/{project_id}")
def update_project(project_id: int, project: ProjectUpdate, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "project not found")

    updates = project.model_dump(exclude_unset=True)
    if not updates:
        return dict(existing)

    if "status" in updates and updates["status"] not in ("active", "paused"):
        raise HTTPException(400, "status must be 'active' or 'paused'")
    if "path" in updates and not _path_exists(updates["path"]):
        raise HTTPException(
            400,
            f"path does not exist: {updates['path']} — if this is running in Docker, "
            "the folder needs to be bind-mounted (see REPO_MOUNTS in docker-compose.yml)",
        )

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [project_id]
    conn.execute(
        f"UPDATE projects SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


@router.delete("/{project_id}")
def deactivate_project(project_id: int, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "project not found")
    conn.execute(
        "UPDATE projects SET status = 'paused', updated_at = datetime('now') WHERE id = ?",
        (project_id,),
    )
    conn.commit()
    return {"ok": True}
