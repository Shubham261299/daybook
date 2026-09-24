import calendar
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends

from dashboard.backend.deps import get_db
from dashboard.backend.routes.projects import _with_quiet_flag
from summarizer.backfill import find_missing_summary_dates

router = APIRouter()


@router.get("")
def get_overview(conn: sqlite3.Connection = Depends(get_db)):
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1]).isoformat()

    project_rows = conn.execute(
        """
        SELECT p.*, MAX(date(c.authored_at)) AS last_commit_date
        FROM projects p
        LEFT JOIN commits c ON c.project_id = p.id
        GROUP BY p.id
        ORDER BY p.name
        """
    ).fetchall()
    projects = [_with_quiet_flag(dict(r)) for r in project_rows]
    active_projects = [p for p in projects if p["status"] == "active"]

    day_counts = conn.execute(
        """
        SELECT date(authored_at) AS d, count(*) AS c
        FROM commits WHERE date(authored_at) BETWEEN ? AND ?
        GROUP BY d
        """,
        (month_start, month_end),
    ).fetchall()
    count_by_day = {r["d"]: r["c"] for r in day_counts}
    total_commits_this_month = sum(count_by_day.values())

    days_in_month = calendar.monthrange(today.year, today.month)[1]
    sparkline = [
        count_by_day.get(today.replace(day=d).isoformat(), 0)
        for d in range(1, days_in_month + 1)
    ]

    recent_summary_row = conn.execute(
        """
        SELECT * FROM daily_summaries
        WHERE project_bullets IS NOT NULL AND project_bullets != '[]'
        ORDER BY summary_date DESC LIMIT 1
        """
    ).fetchone()

    return {
        "active_project_count": len(active_projects),
        "total_commits_this_month": total_commits_this_month,
        "sparkline_this_month": sparkline,
        "projects": projects,
        "quiet_projects": [p for p in active_projects if p["is_quiet"]],
        "recent_summary": dict(recent_summary_row) if recent_summary_row else None,
        "missing_summary_dates": find_missing_summary_dates(conn),
    }
