import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.backend.deps import get_db
from summarizer.generate_rollup import generate_rollup_summary, week_bounds, month_bounds

router = APIRouter()


@router.get("/bounds")
def bounds(period_type: str, which: str):
    if period_type not in ("week", "month"):
        raise HTTPException(400, "period_type must be 'week' or 'month'")
    if which not in ("this", "last"):
        raise HTTPException(400, "which must be 'this' or 'last'")
    fn = week_bounds if period_type == "week" else month_bounds
    start, end = fn(which)
    return {"period_start": start, "period_end": end}


@router.get("")
def get_rollup(period_type: str, period_start: str, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute(
        "SELECT * FROM rollup_summaries WHERE period_type = ? AND period_start = ?",
        (period_type, period_start),
    ).fetchone()
    return dict(row) if row else None


class RollupGenerate(BaseModel):
    period_type: str
    period_start: str
    period_end: str


@router.post("/generate")
def generate(body: RollupGenerate, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return generate_rollup_summary(body.period_type, body.period_start, body.period_end)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"rollup generation failed: {e}")


class RollupEdit(BaseModel):
    narrative: str | None = None
    project_bullets: list | None = None
    other_activities: list | None = None


@router.patch("")
def edit_rollup(period_type: str, period_start: str, edit: RollupEdit, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute(
        "SELECT * FROM rollup_summaries WHERE period_type = ? AND period_start = ?",
        (period_type, period_start),
    ).fetchone()
    if not existing:
        raise HTTPException(404, "no rollup exists for this period yet — generate one first")

    updates = edit.model_dump(exclude_unset=True)
    if not updates:
        return dict(existing)

    set_parts = []
    values = []
    for k, v in updates.items():
        set_parts.append(f"{k} = ?")
        values.append(json.dumps(v) if k in ("project_bullets", "other_activities") else v)
    values.extend([period_type, period_start])

    conn.execute(
        f"UPDATE rollup_summaries SET {', '.join(set_parts)}, edited = 1 WHERE period_type = ? AND period_start = ?",
        values,
    )
    conn.commit()
    return dict(conn.execute(
        "SELECT * FROM rollup_summaries WHERE period_type = ? AND period_start = ?",
        (period_type, period_start),
    ).fetchone())
