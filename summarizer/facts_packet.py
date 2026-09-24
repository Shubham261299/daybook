"""Builds a compact 'facts packet' (commit messages + stats + notes, NOT full
diffs) for a date range and optional project filter. Used both for the daily
summary (range = single day) and the ask-anything chat (arbitrary range).
"""
import sqlite3


def build_facts_packet(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
    project_id: int | None = None,
) -> dict:
    project_filter = ""
    params: list = [start_date, end_date]
    if project_id:
        project_filter = "AND c.project_id = ?"
        params.append(project_id)

    commit_rows = conn.execute(
        f"""
        SELECT c.*, p.name AS project_name
        FROM commits c
        JOIN projects p ON p.id = c.project_id
        WHERE date(c.authored_at) BETWEEN ? AND ?
        {project_filter}
        ORDER BY p.name, c.authored_at
        """,
        params,
    ).fetchall()

    projects: dict[str, list[dict]] = {}
    for r in commit_rows:
        projects.setdefault(r["project_name"], []).append({
            "hash": r["commit_hash"][:7],
            "message": r["message"],
            "files_changed": r["files_changed"],
            "insertions": r["insertions"],
            "deletions": r["deletions"],
            "authored_at": r["authored_at"],
        })

    note_params: list = [start_date, end_date]
    note_filter = ""
    if project_id:
        note_filter = "AND note.project_id = ?"
        note_params.append(project_id)

    note_rows = conn.execute(
        f"""
        SELECT note.*, p.name AS project_name
        FROM notes note
        LEFT JOIN projects p ON p.id = note.project_id
        WHERE note.note_date BETWEEN ? AND ?
        {note_filter}
        ORDER BY note.note_date, note.created_at
        """,
        note_params,
    ).fetchall()

    notes = [{
        "date": r["note_date"],
        "text": r["text"],
        "tag": r["tag"],
        "duration_minutes": r["duration_minutes"],
        "project": r["project_name"],
    } for r in note_rows]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "projects": [
            {"name": name, "commits": commits} for name, commits in projects.items()
        ],
        "notes": notes,
    }


def format_facts_packet_text(packet: dict) -> str:
    lines = [f"Date range: {packet['start_date']} to {packet['end_date']}", ""]

    if not packet["projects"] and not packet["notes"]:
        lines.append("(No commits or notes recorded in this range.)")
        return "\n".join(lines)

    if packet["projects"]:
        lines.append("COMMITS BY PROJECT:")
        for proj in packet["projects"]:
            lines.append(f"\n[{proj['name']}]")
            for c in proj["commits"]:
                subject = (c["message"] or "").split("\n", 1)[0]
                lines.append(
                    f"- {c['authored_at'][:16]} ({c['hash']}) {subject} "
                    f"[+{c['insertions']}/-{c['deletions']}, {c['files_changed']} file(s)]"
                )
    else:
        lines.append("COMMITS: none in this range.")

    lines.append("")
    if packet["notes"]:
        lines.append("NOTES:")
        for n in packet["notes"]:
            tag = f" [{n['tag']}]" if n["tag"] else ""
            dur = f" ({n['duration_minutes']} min)" if n["duration_minutes"] else ""
            proj = f" (re: {n['project']})" if n["project"] else ""
            lines.append(f"- {n['date']}{tag}{dur}{proj}: {n['text']}")
    else:
        lines.append("NOTES: none in this range.")

    return "\n".join(lines)
