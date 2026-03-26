import os
import threading
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

from app.database.repository import Repository
from app.database.connection import engine
from app.database.models import Base

REQUIRED_ENV_VARS = [
    "CEREBRAS_API_KEY",
    "MY_EMAIL",
    "APP_PASSWORD",
]

# In-memory pipeline status
_pipeline_status = {
    "running": False,
    "last_run": None,
    "last_result": None
}


def _run_pipeline_sync(hours: int = 24, top_n: int = 10):
    from app.daily_runner import run_daily_pipeline
    if _pipeline_status["running"]:
        return
    _pipeline_status["running"] = True
    try:
        result = run_daily_pipeline(hours=hours, top_n=top_n)
        _pipeline_status["last_result"] = result
        _pipeline_status["last_run"] = datetime.now().isoformat()
    finally:
        _pipeline_status["running"] = False


# Scheduler: runs pipeline every day at 8:00 AM
scheduler = BackgroundScheduler()
scheduler.add_job(
    _run_pipeline_sync,
    trigger="cron",
    hour=8,
    minute=0,
    id="daily_pipeline",
    replace_existing=True
)


def _validate_required_env_vars() -> None:
    missing = [key for key in REQUIRED_ENV_VARS if not os.getenv(key)]
    if missing:
        missing_keys = ", ".join(sorted(missing))
        raise RuntimeError(f"Missing required environment variables: {missing_keys}")


def _initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _should_run_startup_catchup() -> bool:
    run_on_startup = os.getenv("RUN_PIPELINE_ON_STARTUP", "true").lower() in {"1", "true", "yes"}
    if not run_on_startup:
        return False

    startup_mode = os.getenv("RUN_PIPELINE_STARTUP_MODE", "always").lower()
    if startup_mode == "always":
        return True
    if startup_mode != "daily":
        return False

    schedule_hour = int(os.getenv("PIPELINE_SCHEDULE_HOUR", "8"))
    now = datetime.now()
    if now.hour < schedule_hour:
        return False

    with engine.connect() as connection:
        last_digest_created_at = connection.execute(text("SELECT MAX(created_at) FROM digests")).scalar()

    if not last_digest_created_at:
        return True

    return last_digest_created_at.date() < now.date()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_required_env_vars()
    _initialize_database()
    scheduler.start()
    print("Scheduler started — pipeline will run daily at 8:00 AM")

    if _should_run_startup_catchup() and not _pipeline_status["running"]:
        startup_hours = int(os.getenv("PIPELINE_STARTUP_HOURS", "24"))
        startup_top_n = int(os.getenv("PIPELINE_STARTUP_TOP_N", "10"))
        print("Startup catch-up: running pipeline once after restart")
        threading.Thread(
            target=_run_pipeline_sync,
            kwargs={"hours": startup_hours, "top_n": startup_top_n},
            daemon=True,
        ).start()

    yield
    if scheduler.running:
        scheduler.shutdown()
    print("Scheduler stopped")


app = FastAPI(
    title="AI News Aggregator",
    description="Scrapes, summarizes, and emails AI news digests daily",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineRequest(BaseModel):
    hours: int = 24
    top_n: int = 10


@app.get("/")
def root():
    return {"message": "AI News Aggregator API", "docs": "/docs"}


@app.post("/run-pipeline")
def run_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    if _pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline is already running")
    background_tasks.add_task(_run_pipeline_sync, request.hours, request.top_n)
    return {"message": "Pipeline started", "hours": request.hours, "top_n": request.top_n}


@app.get("/status")
def get_status():
    next_run = None
    job = scheduler.get_job("daily_pipeline")
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()
    return {
        "running": _pipeline_status["running"],
        "last_run": _pipeline_status["last_run"],
        "last_result": _pipeline_status["last_result"],
        "next_scheduled_run": next_run
    }


@app.get("/digests")
def get_digests(hours: int = 24):
    repo = Repository()
    digests = repo.get_recent_digests(hours=hours)
    return {"count": len(digests), "digests": digests}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
