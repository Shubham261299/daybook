"""Weekly/monthly rollup generation, built the same way as a daily summary
but over a wider date range.
"""
import calendar
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection
from summarizer.generate_summary import generate_range_narrative


def week_bounds(period: str, today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    if period == "this":
        return monday.isoformat(), today.isoformat()
    if period == "last":
        last_monday = monday - timedelta(days=7)
        last_sunday = monday - timedelta(days=1)
        return last_monday.isoformat(), last_sunday.isoformat()
    raise ValueError("period must be 'this' or 'last'")


def month_bounds(period: str, today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    if period == "this":
        return today.replace(day=1).isoformat(), today.isoformat()
    if period == "last":
        last_day_prev = today.replace(day=1) - timedelta(days=1)
        first_day_prev = last_day_prev.replace(day=1)
        return first_day_prev.isoformat(), last_day_prev.isoformat()
    raise ValueError("period must be 'this' or 'last'")


def generate_rollup_summary(period_type: str, period_start: str, period_end: str, model: str | None = None) -> dict:
    if period_type not in ("week", "month"):
        raise ValueError("period_type must be 'week' or 'month'")

    conn = get_connection()
    try:
        label = "week" if period_type == "week" else "month"
        result = generate_range_narrative(conn, period_start, period_end, label, model=model)
        generated_at = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT INTO rollup_summaries
                (period_type, period_start, period_end, narrative, project_bullets, other_activities, model_used, generated_at, edited)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(period_type, period_start) DO UPDATE SET
                period_end = excluded.period_end,
                narrative = excluded.narrative,
                project_bullets = excluded.project_bullets,
                other_activities = excluded.other_activities,
                model_used = excluded.model_used,
                generated_at = excluded.generated_at,
                edited = 0
            """,
            (
                period_type, period_start, period_end, result["narrative"],
                json.dumps(result["project_bullets"]), json.dumps(result["other_activities"]),
                result["model_used"], generated_at,
            ),
        )
        conn.commit()

        return {
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": generated_at,
            **result,
        }
    finally:
        conn.close()
