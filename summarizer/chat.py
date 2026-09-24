"""Ask-anything chat: turns a free-text question into a structured date range
+ optional project filter (deterministic heuristics, not LLM — local small
models are unreliable at date arithmetic), retrieves facts via SQL, and asks
Ollama to answer using only that retrieved context. Stateless (no persisted
chat history) for v1.
"""
import calendar
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from summarizer.facts_packet import build_facts_packet, format_facts_packet_text
from summarizer.ollama_client import generate, MODEL

SYSTEM_PROMPT = """You are a helpful assistant answering questions about the user's own \
past work, based on git commit activity and personal notes provided below. Only use the \
information given — do not invent commits, dates, or details. If the provided data doesn't \
answer the question, say so plainly. Answer conversationally, in a few sentences or a short \
bulleted list as appropriate. Refer to projects by name.
"""


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def parse_date_range(question: str, today: date) -> tuple[str, str]:
    q = question.lower()

    m = re.search(r"last (\d+)\s*days?", q) or re.search(r"past (\d+)\s*days?", q)
    if m:
        n = int(m.group(1))
        return (today - timedelta(days=n)).isoformat(), today.isoformat()

    m = re.search(r"(\d{4}-\d{2}-\d{2}).{0,10}(?:to|and|-|through)\s*.{0,10}(\d{4}-\d{2}-\d{2})", q)
    if m:
        return m.group(1), m.group(2)

    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q)
    if m and ("since" in q or "from" in q or "on" in q):
        d = m.group(1)
        if "on" in q:
            return d, d
        return d, today.isoformat()

    if "yesterday" in q:
        y = today - timedelta(days=1)
        return y.isoformat(), y.isoformat()

    if "today" in q:
        return today.isoformat(), today.isoformat()

    if "last week" in q:
        this_monday = _monday_of(today)
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        return last_monday.isoformat(), last_sunday.isoformat()

    if "this week" in q:
        return _monday_of(today).isoformat(), today.isoformat()

    if "last month" in q:
        first_of_this_month = today.replace(day=1)
        last_day_prev_month = first_of_this_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        return first_day_prev_month.isoformat(), last_day_prev_month.isoformat()

    if "this month" in q:
        return today.replace(day=1).isoformat(), today.isoformat()

    # default: last 30 days
    return (today - timedelta(days=30)).isoformat(), today.isoformat()


_PHASE_ALIASES = {
    "phase 1": "Phase I", "phase i": "Phase I", "phase-1": "Phase I",
    "phase 2": "Phase II", "phase ii": "Phase II", "phase-2": "Phase II",
    "phase 3": "Phase III", "phase iii": "Phase III", "phase-3": "Phase III",
}


def parse_project(question: str, projects: list[sqlite3.Row]) -> sqlite3.Row | None:
    q = question.lower()

    for alias, phase in _PHASE_ALIASES.items():
        if alias in q:
            for p in projects:
                if p["phase"] == phase:
                    return p

    for p in projects:
        if p["name"].lower() in q:
            return p
        if p["phase"] and p["phase"].lower() in q:
            return p

    if "dashboard" in q:
        for p in projects:
            if "dashboard" in p["name"].lower():
                return p

    return None


def ask(conn: sqlite3.Connection, question: str, today: date | None = None, model: str | None = None) -> dict:
    today = today or date.today()

    projects = conn.execute("SELECT * FROM projects").fetchall()
    project = parse_project(question, projects)
    start_date, end_date = parse_date_range(question, today)

    packet = build_facts_packet(conn, start_date, end_date, project["id"] if project else None)
    facts_text = format_facts_packet_text(packet)

    summary_rows = conn.execute(
        "SELECT summary_date, narrative FROM daily_summaries WHERE summary_date BETWEEN ? AND ? ORDER BY summary_date",
        (start_date, end_date),
    ).fetchall()
    if summary_rows:
        facts_text += "\n\nEXISTING DAILY SUMMARIES:\n" + "\n".join(
            f"- {r['summary_date']}: {r['narrative']}" for r in summary_rows if r["narrative"]
        )

    prompt = f"Question: {question}\n\nData:\n{facts_text}"
    answer = generate(prompt, model=model or MODEL, system=SYSTEM_PROMPT)

    return {
        "answer": answer,
        "interpreted_range": {"start_date": start_date, "end_date": end_date},
        "interpreted_project": project["name"] if project else None,
    }
