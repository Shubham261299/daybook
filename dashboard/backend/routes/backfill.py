import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends

from dashboard.backend.deps import get_db
from summarizer.backfill import find_missing_summary_dates, backfill_summaries

router = APIRouter()


@router.get("/missing")
def missing(conn: sqlite3.Connection = Depends(get_db)):
    return {"missing_dates": find_missing_summary_dates(conn)}


@router.post("/run")
def run(background_tasks: BackgroundTasks, conn: sqlite3.Connection = Depends(get_db)):
    dates = find_missing_summary_dates(conn)
    background_tasks.add_task(backfill_summaries, dates)
    return {"queued_dates": dates}
