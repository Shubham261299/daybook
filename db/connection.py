"""SQLite connection helper. Applies schema.sql on first use."""
import sqlite3
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", "./data/activity.db"))
if not DB_PATH.is_absolute():
    DB_PATH = (BASE_DIR / DB_PATH).resolve()

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI can resolve a sync dependency and run
    # the sync endpoint on different threadpool workers, even though each
    # request-scoped connection is only ever used serially within one
    # request (created in get_db(), used by the endpoint, closed after).
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Small additive schema tweaks for DBs created before a column existed.
    schema.sql's CREATE TABLE IF NOT EXISTS won't touch an already-existing
    table, so new columns need an explicit ALTER TABLE here.
    """
    project_columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
    if "department" not in project_columns:
        conn.execute("ALTER TABLE projects ADD COLUMN department TEXT")

    task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "project_id" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL")

    conn.commit()


def init_db() -> None:
    conn = get_connection()
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
        _run_migrations(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
