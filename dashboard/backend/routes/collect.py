import sqlite3

from fastapi import APIRouter, Depends

from dashboard.backend.deps import get_db
from collector.collect import collect_for_project

router = APIRouter()


@router.post("")
def run_collect(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM projects WHERE status = 'active'").fetchall()

    results = []
    total_new = 0
    for row in rows:
        new_count = collect_for_project(conn, row)
        results.append({"project": row["name"], "new_commits": new_count})
        total_new += new_count

    return {"total_new_commits": total_new, "projects": results}
