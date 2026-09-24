"""Summary generation shared by daily and rollup (weekly/monthly) summaries:
facts packet for a date range -> Ollama -> parsed narrative + project-wise
bullets + other-activities.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection
from summarizer.facts_packet import build_facts_packet, format_facts_packet_text
from summarizer.ollama_client import generate, MODEL


class ProjectBullets(BaseModel):
    project: str
    bullets: list[str]


class SummaryOutput(BaseModel):
    narrative: str
    projects: list[ProjectBullets] = []
    other_activities: list[str] = []


def build_system_prompt(period_label: str) -> str:
    return f"""You are a concise work-journal assistant. You are given a {period_label}'s git \
commit activity (grouped by project) and free-text notes (meetings, demos, discussions). \
Respond with JSON matching the required schema:

- narrative: a short paragraph (2-5 sentences) summarizing the {period_label} overall, in first person past tense.
- projects: one entry per project that actually has commits, each with the project's exact name and a list of \
short factual bullet points describing what was done, based on the commits. Omit projects with no commits.
- other_activities: bullet points derived from notes (meetings/demos/discussions/etc). Leave empty if there are no notes.

Rules:
- Do not invent details not present in the commits or notes.
- Keep bullets short and factual, not marketing language.
- If there is a lot of activity, prefer a handful of higher-level bullets per project over listing every single commit.
"""


def parse_structured_output(text: str) -> tuple[str, list[dict], list[str]]:
    """Ollama grammar-constrains sampling against SummaryOutput's schema (see
    the `format` param passed to generate()), so this should always be
    valid JSON matching the schema — the try/except below is just a
    boundary guard against a malformed or empty response, not the primary
    parsing strategy.
    """
    try:
        parsed = SummaryOutput.model_validate_json(text)
    except (ValidationError, ValueError):
        return text.strip(), [], []
    return parsed.narrative, [p.model_dump() for p in parsed.projects], parsed.other_activities


def generate_range_narrative(conn, start_date: str, end_date: str, period_label: str, model: str | None = None) -> dict:
    """Builds a facts packet for [start_date, end_date] and asks Ollama to
    narrate it. Does not touch the DB beyond reading — callers persist the
    result into whichever table (daily_summaries / rollup_summaries) fits.
    """
    packet = build_facts_packet(conn, start_date, end_date)
    facts_text = format_facts_packet_text(packet)

    if not packet["projects"] and not packet["notes"]:
        return {
            "narrative": f"No commits or notes recorded for this {period_label}.",
            "project_bullets": [],
            "other_activities": [],
            "model_used": None,
        }

    model_used = model or MODEL
    raw = generate(
        facts_text,
        model=model_used,
        system=build_system_prompt(period_label),
        format=SummaryOutput.model_json_schema(),
    )
    narrative, project_bullets, other_activities = parse_structured_output(raw)
    return {
        "narrative": narrative,
        "project_bullets": project_bullets,
        "other_activities": other_activities,
        "model_used": model_used,
    }


def generate_daily_summary(summary_date: str, model: str | None = None) -> dict:
    conn = get_connection()
    try:
        result = generate_range_narrative(conn, summary_date, summary_date, "day", model=model)
        generated_at = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT INTO daily_summaries
                (summary_date, narrative, project_bullets, other_activities, model_used, generated_at, edited)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(summary_date) DO UPDATE SET
                narrative = excluded.narrative,
                project_bullets = excluded.project_bullets,
                other_activities = excluded.other_activities,
                model_used = excluded.model_used,
                generated_at = excluded.generated_at,
                edited = 0
            """,
            (
                summary_date, result["narrative"], json.dumps(result["project_bullets"]),
                json.dumps(result["other_activities"]), result["model_used"], generated_at,
            ),
        )
        conn.commit()

        return {
            "summary_date": summary_date,
            "generated_at": generated_at,
            **result,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="YYYY-MM-DD")
    args = parser.parse_args()
    result = generate_daily_summary(args.date)
    print(json.dumps(result, indent=2))
