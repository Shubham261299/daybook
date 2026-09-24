import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.backend.deps import get_db
from summarizer.generate_summary import generate_daily_summary

router = APIRouter()


class SummaryEdit(BaseModel):
    narrative: str | None = None
    project_bullets: list | None = None
    other_activities: list | None = None


@router.post("/{day}/generate")
def generate(day: str, conn: sqlite3.Connection = Depends(get_db)):
    try:
        result = generate_daily_summary(day)
    except Exception as e:
        raise HTTPException(502, f"summary generation failed: {e}")
    return result


@router.patch("/{day}")
def edit_summary(day: str, edit: SummaryEdit, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute("SELECT * FROM daily_summaries WHERE summary_date = ?", (day,)).fetchone()
    if not existing:
        raise HTTPException(404, "no summary exists for this day yet — generate one first")

    updates = edit.model_dump(exclude_unset=True)
    if not updates:
        return dict(existing)

    set_parts = []
    values = []
    for k, v in updates.items():
        set_parts.append(f"{k} = ?")
        values.append(json.dumps(v) if k in ("project_bullets", "other_activities") else v)
    values.append(day)

    conn.execute(
        f"UPDATE daily_summaries SET {', '.join(set_parts)}, edited = 1 WHERE summary_date = ?",
        values,
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM daily_summaries WHERE summary_date = ?", (day,)).fetchone())
