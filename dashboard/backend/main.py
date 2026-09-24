import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from db.connection import init_db, get_connection
from dashboard.backend.auth import BasicAuthMiddleware
from dashboard.backend.routes import projects, notes, days, summaries, chat, rollups, export, collect, overview, backfill, tasks

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

init_db()

# Opt-in background collection loop — off (0) by default so native installs
# that already run the collector via Task Scheduler don't double up. Set
# COLLECT_INTERVAL_SECONDS to enable (docker-compose.yml turns this on so the
# container is fully self-contained, no host scheduler needed).
COLLECT_INTERVAL_SECONDS = int(os.getenv("COLLECT_INTERVAL_SECONDS", "0"))


async def _periodic_collect_loop():
    from collector.collect import collect_for_project

    while True:
        await asyncio.sleep(COLLECT_INTERVAL_SECONDS)
        try:
            conn = get_connection()
            try:
                rows = conn.execute("SELECT * FROM projects WHERE status = 'active'").fetchall()
                for row in rows:
                    collect_for_project(conn, row)
            finally:
                conn.close()
        except Exception as e:
            print(f"[periodic-collect] error: {e}")


# End-of-day job — off (-1) by default. Set EOD_HOUR (0-23, local time) to
# have this instance automatically collect + generate that day's summary
# once a day. Skips generation if the day already has a manually-edited
# summary, so it won't clobber a hand-tweaked draft.
EOD_HOUR = int(os.getenv("EOD_HOUR", "-1"))


async def _eod_job():
    from collector.collect import collect_for_project
    from summarizer.generate_summary import generate_daily_summary

    while True:
        now = datetime.now()
        target = now.replace(hour=EOD_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

        try:
            today = date.today().isoformat()
            conn = get_connection()
            try:
                rows = conn.execute("SELECT * FROM projects WHERE status = 'active'").fetchall()
                for row in rows:
                    collect_for_project(conn, row)

                existing = conn.execute(
                    "SELECT edited FROM daily_summaries WHERE summary_date = ?", (today,)
                ).fetchone()
            finally:
                conn.close()

            if existing and existing["edited"]:
                print(f"[eod-job] skipping {today} — has a manually-edited summary")
            else:
                generate_daily_summary(today)
        except Exception as e:
            print(f"[eod-job] error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    if COLLECT_INTERVAL_SECONDS > 0:
        tasks.append(asyncio.create_task(_periodic_collect_loop()))
    if 0 <= EOD_HOUR <= 23:
        tasks.append(asyncio.create_task(_eod_job()))
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Daybook Shubham", lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)


@app.middleware("http")
async def no_cache_static(request, call_next):
    # This app changes often during development — force every static asset
    # to be refetched rather than trusting any cache in between (browser or
    # intermediate proxy) serving stale JS after a rebuild.
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(days.router, prefix="/api/days", tags=["days"])
app.include_router(summaries.router, prefix="/api/summaries", tags=["summaries"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(rollups.router, prefix="/api/rollups", tags=["rollups"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(collect.router, prefix="/api/sync", tags=["collect"])  # not /api/collect —
# ad blockers / security extensions commonly block any URL containing "collect"
# (it's the standard analytics-tracking endpoint name: Google Analytics, Segment, etc. all
# use exactly that word), silently — no response, nothing in the server log, just gone
app.include_router(overview.router, prefix="/api/overview", tags=["overview"])
app.include_router(backfill.router, prefix="/api/backfill", tags=["backfill"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/settings")
def settings_page():
    return FileResponse(str(FRONTEND_DIR / "settings.html"))


@app.get("/ask")
def ask_page():
    return FileResponse(str(FRONTEND_DIR / "ask.html"))


@app.get("/dashboard")
def dashboard_page():
    return FileResponse(str(FRONTEND_DIR / "overview.html"))


@app.get("/tasks")
def tasks_page():
    return FileResponse(str(FRONTEND_DIR / "tasks.html"))


if __name__ == "__main__":
    import os
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()
    uvicorn.run(
        "dashboard.backend.main:app",
        host=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
        port=int(os.getenv("DASHBOARD_PORT", "8000")),
    )
