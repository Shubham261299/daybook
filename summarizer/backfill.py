"""Bulk-generate daily summaries for past days that have commits or notes but
no summary yet. Each generation is an LLM call (15-60+s), so this is meant to
run in the background (API) or from a terminal (CLI) — never as a blocking
request a browser waits on.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection
from summarizer.generate_summary import generate_daily_summary


def find_missing_summary_dates(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT d FROM (
            SELECT date(authored_at) AS d FROM commits
            UNION
            SELECT note_date AS d FROM notes
        )
        WHERE d NOT IN (SELECT summary_date FROM daily_summaries)
        ORDER BY d
        """
    ).fetchall()
    return [r["d"] for r in rows]


def backfill_summaries(dates: list[str] | None = None, model: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        target_dates = dates if dates is not None else find_missing_summary_dates(conn)
    finally:
        conn.close()

    results = []
    for d in target_dates:
        try:
            generate_daily_summary(d, model=model)
            results.append({"date": d, "ok": True})
        except Exception as e:
            results.append({"date": d, "ok": False, "error": str(e)})
    return results


if __name__ == "__main__":
    conn = get_connection()
    missing = find_missing_summary_dates(conn)
    conn.close()

    if not missing:
        print("No missing summaries — every day with activity already has one.")
    else:
        print(f"Backfilling {len(missing)} day(s): {', '.join(missing)}")
        for i, d in enumerate(missing, 1):
            print(f"[{i}/{len(missing)}] {d}...", end=" ", flush=True)
            try:
                generate_daily_summary(d)
                print("done")
            except Exception as e:
                print(f"FAILED: {e}")
        print("Backfill complete.")
