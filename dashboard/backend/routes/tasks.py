import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.backend.deps import get_db

router = APIRouter()


class TaskIn(BaseModel):
    text: str
    due_date: str | None = None
    project_id: int | None = None


class TaskUpdate(BaseModel):
    text: str | None = None
    due_date: str | None = None
    status: str | None = None
    project_id: int | None = None


@router.get("")
def list_tasks(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        """
        SELECT t.*, p.name AS project_name
        FROM tasks t
        LEFT JOIN projects p ON p.id = t.project_id
        ORDER BY
            t.status ASC,
            CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,
            t.due_date ASC,
            t.created_at ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("")
def create_task(task: TaskIn, conn: sqlite3.Connection = Depends(get_db)):
    if not task.text.strip():
        raise HTTPException(400, "text cannot be empty")
    cur = conn.execute(
        "INSERT INTO tasks (text, due_date, project_id) VALUES (?, ?, ?)",
        (task.text.strip(), task.due_date, task.project_id),
    )
    conn.commit()
    return {"id": cur.lastrowid}


@router.patch("/{task_id}")
def update_task(task_id: int, task: TaskUpdate, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "task not found")

    updates = task.model_dump(exclude_unset=True)
    if not updates:
        return dict(existing)

    if "status" in updates and updates["status"] not in ("open", "done"):
        raise HTTPException(400, "status must be 'open' or 'done'")

    set_parts = [f"{k} = ?" for k in updates]
    values = list(updates.values())

    if "status" in updates:
        set_parts.append("completed_at = " + ("datetime('now')" if updates["status"] == "done" else "NULL"))

    values.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ?", values)
    conn.commit()
    return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


@router.delete("/{task_id}")
def delete_task(task_id: int, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "task not found")
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return {"ok": True}
