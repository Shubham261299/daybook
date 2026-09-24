import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from dashboard.backend.deps import get_db
from summarizer.facts_packet import build_facts_packet

router = APIRouter()


def _render_markdown(title: str, summary_row, start_date: str, end_date: str, packet: dict) -> str:
    lines = [f"# {title}", ""]

    if summary_row and summary_row["narrative"]:
        lines.append(summary_row["narrative"])
        lines.append("")
        try:
            bullets = json.loads(summary_row["project_bullets"] or "[]")
        except (TypeError, ValueError):
            bullets = []
        for pb in bullets:
            lines.append(f"### {pb['project']}")
            for b in pb["bullets"]:
                lines.append(f"- {b}")
            lines.append("")
        try:
            other = json.loads(summary_row["other_activities"] or "[]")
        except (TypeError, ValueError):
            other = []
        if other:
            lines.append("### Other activities")
            for b in other:
                lines.append(f"- {b}")
            lines.append("")
    else:
        lines.append("_No generated summary for this period — raw activity below._")
        lines.append("")

    lines.append("## Commits")
    if packet["projects"]:
        for proj in packet["projects"]:
            lines.append(f"### {proj['name']}")
            for c in proj["commits"]:
                lines.append(f"- `{c['hash']}` {c['message']} (+{c['insertions']}/-{c['deletions']})")
            lines.append("")
    else:
        lines.append("_No commits in this period._")
        lines.append("")

    if packet["notes"]:
        lines.append("## Notes")
        for n in packet["notes"]:
            tag = f"[{n['tag']}] " if n["tag"] else ""
            proj = f" (re: {n['project']})" if n["project"] else ""
            lines.append(f"- {n['date']}: {tag}{n['text']}{proj}")
        lines.append("")

    return "\n".join(lines)


def _md_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/day/{day}")
def export_day(day: str, conn: sqlite3.Connection = Depends(get_db)):
    summary_row = conn.execute("SELECT * FROM daily_summaries WHERE summary_date = ?", (day,)).fetchone()
    packet = build_facts_packet(conn, day, day)
    md = _render_markdown(f"Work summary — {day}", summary_row, day, day, packet)
    return _md_response(md, f"{day}-summary.md")


@router.get("/rollup")
def export_rollup(period_type: str, period_start: str, conn: sqlite3.Connection = Depends(get_db)):
    if period_type not in ("week", "month"):
        raise HTTPException(400, "period_type must be 'week' or 'month'")
    row = conn.execute(
        "SELECT * FROM rollup_summaries WHERE period_type = ? AND period_start = ?",
        (period_type, period_start),
    ).fetchone()
    end_date = row["period_end"] if row else period_start
    packet = build_facts_packet(conn, period_start, end_date)
    title = f"Work summary — {period_type} of {period_start} to {end_date}"
    md = _render_markdown(title, row, period_start, end_date, packet)
    return _md_response(md, f"{period_type}-{period_start}-summary.md")
