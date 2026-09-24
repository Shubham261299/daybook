import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from db.connection import get_connection


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
