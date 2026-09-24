import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.backend.deps import get_db

router = APIRouter()

VALID_TAGS = {"meeting", "demo", "discussion", "blocker", "idea"}


class NoteIn(BaseModel):
    note_date: str  # YYYY-MM-DD
    text: str
    duration_minutes: int | None = None
    tag: str | None = None
    project_id: int | None = None


@router.get("")
def list_notes(note_date: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    if note_date:
        rows = conn.execute(
            "SELECT * FROM notes WHERE note_date = ? ORDER BY created_at", (note_date,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notes ORDER BY note_date DESC, created_at DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("")
def create_note(note: NoteIn, conn: sqlite3.Connection = Depends(get_db)):
    if note.tag and note.tag not in VALID_TAGS:
        raise HTTPException(400, f"tag must be one of {sorted(VALID_TAGS)}")
    if not note.text.strip():
        raise HTTPException(400, "text cannot be empty")

    cur = conn.execute(
        "INSERT INTO notes (note_date, text, duration_minutes, tag, project_id) VALUES (?, ?, ?, ?, ?)",
        (note.note_date, note.text.strip(), note.duration_minutes, note.tag, note.project_id),
    )
    conn.commit()
    return {"id": cur.lastrowid}


@router.delete("/{note_id}")
def delete_note(note_id: int, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "note not found")
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    return {"ok": True}
