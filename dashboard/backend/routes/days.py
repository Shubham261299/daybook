import calendar
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from dashboard.backend.deps import get_db

router = APIRouter()


@router.get("/overview")
def month_overview(year: int, month: int, conn: sqlite3.Connection = Depends(get_db)):
    if not (1 <= month <= 12):
        raise HTTPException(400, "month must be 1-12")

    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"

    commit_counts = conn.execute(
        """
        SELECT date(authored_at) AS d, count(*) AS c
        FROM commits WHERE date(authored_at) BETWEEN ? AND ?
        GROUP BY d
        """,
        (start, end),
    ).fetchall()
    project_commit_counts = conn.execute(
        """
        SELECT date(c.authored_at) AS d, p.name AS project_name, count(*) AS c
        FROM commits c JOIN projects p ON p.id = c.project_id
        WHERE date(c.authored_at) BETWEEN ? AND ?
        GROUP BY d, p.name
        ORDER BY p.name
        """,
        (start, end),
    ).fetchall()
    note_counts = conn.execute(
        "SELECT note_date AS d, count(*) AS c FROM notes WHERE note_date BETWEEN ? AND ? GROUP BY d",
        (start, end),
    ).fetchall()
    summary_dates = conn.execute(
        "SELECT summary_date AS d FROM daily_summaries WHERE summary_date BETWEEN ? AND ?",
        (start, end),
    ).fetchall()
    tagged_commits = conn.execute(
        """
        SELECT date(authored_at) AS d, git_tags
        FROM commits
        WHERE date(authored_at) BETWEEN ? AND ? AND git_tags IS NOT NULL AND git_tags != ''
        """,
        (start, end),
    ).fetchall()

    commit_map = {r["d"]: r["c"] for r in commit_counts}
    note_map = {r["d"]: r["c"] for r in note_counts}
    summary_set = {r["d"] for r in summary_dates}

    projects_by_day: dict[str, list[dict]] = {}
    for r in project_commit_counts:
        projects_by_day.setdefault(r["d"], []).append({"name": r["project_name"], "count": r["c"]})

    tags_by_day: dict[str, list[str]] = {}
    for r in tagged_commits:
        tags_by_day.setdefault(r["d"], []).extend(t for t in r["git_tags"].split(",") if t)

    days = []
    for day_num in range(1, last_day + 1):
        d = f"{year:04d}-{month:02d}-{day_num:02d}"
        days.append({
            "date": d,
            "commit_count": commit_map.get(d, 0),
            "note_count": note_map.get(d, 0),
            "has_summary": d in summary_set,
            "projects": projects_by_day.get(d, []),
            "tags": tags_by_day.get(d, []),
        })

    return {"year": year, "month": month, "days": days}


@router.get("/heatmap")
def commit_heatmap(weeks: int = 53, conn: sqlite3.Connection = Depends(get_db)):
    """GitHub-style contribution heatmap data: one entry per calendar day
    from `weeks` weeks ago (aligned to the preceding Sunday, so full weeks
    render as clean grid columns) through today. Activity is commits + notes
    across all projects — this is a personal activity view, not scoped to
    one project like the calendar page is.
    """
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7  # date.weekday(): Mon=0..Sun=6
    last_sunday = today - timedelta(days=days_since_sunday)
    start = last_sunday - timedelta(days=7 * (weeks - 1))

    start_str = start.isoformat()
    end_str = today.isoformat()

    commit_rows = conn.execute(
        "SELECT date(authored_at) AS d, count(*) AS c FROM commits WHERE date(authored_at) BETWEEN ? AND ? GROUP BY d",
        (start_str, end_str),
    ).fetchall()
    note_rows = conn.execute(
        "SELECT note_date AS d, count(*) AS c FROM notes WHERE note_date BETWEEN ? AND ? GROUP BY d",
        (start_str, end_str),
    ).fetchall()

    counts: dict[str, int] = {}
    for r in commit_rows:
        counts[r["d"]] = counts.get(r["d"], 0) + r["c"]
    for r in note_rows:
        counts[r["d"]] = counts.get(r["d"], 0) + r["c"]

    days = []
    d = start
    while d <= today:
        iso = d.isoformat()
        days.append({"date": iso, "count": counts.get(iso, 0)})
        d += timedelta(days=1)

    return {"start_date": start_str, "end_date": end_str, "days": days}


@router.get("/{day}")
def day_detail(day: str, conn: sqlite3.Connection = Depends(get_db)):
    commit_rows = conn.execute(
        """
        SELECT c.*, p.name AS project_name
        FROM commits c JOIN projects p ON p.id = c.project_id
        WHERE date(c.authored_at) = ?
        ORDER BY p.name, c.authored_at
        """,
        (day,),
    ).fetchall()

    note_rows = conn.execute(
        """
        SELECT n.*, p.name AS project_name
        FROM notes n LEFT JOIN projects p ON p.id = n.project_id
        WHERE n.note_date = ?
        ORDER BY n.created_at
        """,
        (day,),
    ).fetchall()

    summary_row = conn.execute(
        "SELECT * FROM daily_summaries WHERE summary_date = ?", (day,)
    ).fetchone()

    return {
        "date": day,
        "commits": [dict(r) for r in commit_rows],
        "notes": [dict(r) for r in note_rows],
        "summary": dict(summary_row) if summary_row else None,
    }
