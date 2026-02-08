from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from logging_config import setup_logging

logger = setup_logging()
logger.info("--- APP v2.3.1 STARTING ---")

from db import Base, engine, SessionLocal
from models import Monitor, CheckResult
from messaging import publish_check
from v1_router import router as v1_router
from chatbot_router import router as chatbot_router
from graphql_app import graphql_app
from prometheus_fastapi_instrumentator import Instrumentator
from typing import List

description = """
Web Health Monitor API helps you track the uptime of your services. 🚀

## Monitors
You can **create**, **list**, **update**, and **delete** monitors.

## Checks
View historical check data and trigger manual runs.
"""

app = FastAPI(
    title="Web Health Monitor API",
    description=description,
    version="2.0.0",
    contact={
        "name": "Ops Team",
        "url": "http://health-monitor.io/support",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming Request: {request.method} {request.url}")
    auth = request.headers.get("Authorization")
    if auth:
        logger.info(f"Auth Header: {auth[:10]}...")
    else:
        logger.info("Auth Header: None")

    response = await call_next(request)
    logger.info(f"Response Status: {response.status_code}")
    return response


templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount Versioned APIs and GraphQL
app.include_router(v1_router)
app.include_router(chatbot_router)
app.include_router(graphql_app, prefix="/graphql")

# Initialize Prometheus Metrics
Instrumentator().instrument(app).expose(app)

# Create tables
Base.metadata.create_all(bind=engine)

# Quick Migration: Ensure all columns exist
from sqlalchemy import text

columns_to_add = [
    ("strategy", "VARCHAR DEFAULT 'mobile'"),
    ("perf_score", "FLOAT"),
    ("perf_fcp", "FLOAT"),
    ("perf_lcp", "FLOAT"),
    ("perf_cls", "FLOAT"),
    ("perf_tbt", "FLOAT"),
    ("perf_seo", "FLOAT"),
    ("perf_accessible", "FLOAT"),
    ("perf_best_practices", "FLOAT"),
    ("perf_details", "JSON"),
    ("perf_screenshot", "TEXT"),
    ("perf_thumbnails", "JSON"),
]

with engine.connect() as conn:
    for col_name, col_type in columns_to_add:
        try:
            conn.execute(text(f"SELECT {col_name} FROM monitors LIMIT 1"))
        except Exception:
            logger.info(f"Migrating: Adding '{col_name}' column to monitors table...")
            try:
                conn.execute(
                    text(f"ALTER TABLE monitors ADD COLUMN {col_name} {col_type}")
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to add column {col_name}: {e}")


# -------------------- WebSocket Manager --------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        print(
            f"Broadcast: {message.get('event')} to {len(self.active_connections)} clients",
            flush=True,
        )
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass  # Handle stale connections if any


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- Dashboard (UI) --------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # UI loads data via fetch() from API endpoints
    return templates.TemplateResponse("index.html", {"request": request})


# -------------------- Schemas --------------------
class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    url: HttpUrl
    interval_seconds: int = Field(60, ge=10, le=3600)


class MonitorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    url: HttpUrl | None = None
    interval_seconds: int | None = Field(None, ge=10, le=3600)
    is_active: bool | None = None


# -------------------- API (Legacy Support) --------------------
# These endpoints remain for dashboard compatibility (Backward Compatibility)
@app.post("/monitors", tags=["Legacy"])
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    m = Monitor(
        name=payload.name,
        url=str(payload.url),
        interval_seconds=payload.interval_seconds,
        is_active=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    logger.info(f"Created new monitor: {m.name} ({m.url})")

    # Asynchronous trigger: Push to queue immediately after creation
    try:
        publish_check(m.id, task_type="check")
        publish_check(m.id, task_type="audit")  # Also trigger performance audit
    except Exception as e:
        logger.error(f"Failed to publish initial check/audit for {m.id}: {e}")

    # Notify UI via WebSocket
    asyncio.create_task(
        manager.broadcast({"event": "monitor_created", "monitor_id": m.id})
    )

    return {
        "id": m.id,
        "name": m.name,
        "url": m.url,
        "interval_seconds": m.interval_seconds,
        "is_active": m.is_active,
    }


@app.get("/monitors", tags=["Legacy"])
def list_monitors(db: Session = Depends(get_db)):
    monitors = db.query(Monitor).order_by(Monitor.id.asc()).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "url": m.url,
            "interval_seconds": m.interval_seconds,
            "is_active": m.is_active,
            "perf_score": m.perf_score,
            "perf_fcp": m.perf_fcp,
            "perf_lcp": m.perf_lcp,
            "perf_cls": m.perf_cls,
            "perf_seo": m.perf_seo,
            "perf_accessible": m.perf_accessible,
            "perf_best_practices": m.perf_best_practices,
            "perf_details": m.perf_details,
        }
        for m in monitors
    ]


@app.patch("/monitors/{monitor_id}", tags=["Legacy"])
def update_monitor(
    monitor_id: int, payload: MonitorUpdate, db: Session = Depends(get_db)
):
    m = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")

    if payload.name is not None:
        m.name = payload.name
    if payload.url is not None:
        m.url = str(payload.url)
    if payload.interval_seconds is not None:
        m.interval_seconds = payload.interval_seconds
    if payload.is_active is not None:
        m.is_active = payload.is_active

    db.commit()
    db.refresh(m)
    return {
        "id": m.id,
        "name": m.name,
        "url": m.url,
        "interval_seconds": m.interval_seconds,
        "is_active": m.is_active,
    }


@app.delete("/monitors/{monitor_id}", tags=["Legacy"])
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    # ... previous delete logic ...
    m = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")
    db.delete(m)
    db.commit()
    return {"ok": True}


@app.post("/monitors/{monitor_id}/audit", tags=["Legacy"])
async def trigger_monitor_audit(
    monitor_id: int, strategy: str = "mobile", db: Session = Depends(get_db)
):
    m = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")

    try:
        publish_check(m.id, task_type="audit", strategy=strategy)
        # Notify UI to start countdown
        await manager.broadcast({"event": "monitor_created", "monitor_id": m.id})
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to trigger manual audit for {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue audit")


@app.post("/api/v1/internal/broadcast", include_in_schema=False)
async def internal_broadcast(payload: dict):
    """Internal endpoint for worker to notify UI."""
    await manager.broadcast(payload)
    return {"ok": True}


@app.get("/monitors/{monitor_id}/latest", tags=["Legacy"])
def latest_check(monitor_id: int, db: Session = Depends(get_db)):
    last = (
        db.query(CheckResult)
        .filter(CheckResult.monitor_id == monitor_id)
        .order_by(CheckResult.checked_at.desc())
        .first()
    )
    if not last:
        return {"monitor_id": monitor_id, "message": "No checks yet"}
    return {
        "monitor_id": monitor_id,
        "checked_at": last.checked_at,
        "is_up": last.is_up,
        "status_code": last.status_code,
        "response_ms": last.response_ms,
        "error": last.error,
    }


@app.get("/monitors/{monitor_id}/checks", tags=["Legacy"])
def list_checks(monitor_id: int, limit: int = 50, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    rows = (
        db.query(CheckResult)
        .filter(CheckResult.monitor_id == monitor_id)
        .order_by(CheckResult.checked_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "checked_at": r.checked_at,
            "is_up": r.is_up,
            "status_code": r.status_code,
            "response_ms": r.response_ms,
            "error": r.error,
        }
        for r in rows
    ]


@app.post(
    "/run-once",
    summary="Trigger all checks manually",
    description="Publishes check requests for all active monitors to the distributed worker queue.",
)
async def run_once(db: Session = Depends(get_db)):
    """Manually trigger checks once by pushing all active monitor IDs to the queue."""
    monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
    count = 0
    for m in monitors:
        try:
            publish_check(m.id, task_type="check")
            publish_check(m.id, task_type="audit")
            count += 1
        except Exception as e:
            logger.error(f"Failed to publish check/audit for {m.id}: {e}")

    logger.info(
        f"Manual run-once triggered. Pushed {count} monitor IDs for full audit."
    )

    # Notify UI via WebSocket
    asyncio.create_task(manager.broadcast({"event": "checks_running", "count": count}))

    return {"ok": True, "pushed": count}


# -------------------- Scheduler (Producer) --------------------
scheduler = AsyncIOScheduler()


async def _job():
    """Periodic job that pushes monitor IDs to the queue for health checks."""
    db = SessionLocal()
    try:
        monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
        for m in monitors:
            try:
                publish_check(m.id, task_type="check")
            except Exception as e:
                logger.error(f"Producer failed for monitor {m.id}: {e}")
    finally:
        db.close()


async def _audit_job():
    """Periodic job for performance audits (every hour)."""
    db = SessionLocal()
    try:
        monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
        for m in monitors:
            try:
                publish_check(m.id, task_type="audit")
            except Exception as e:
                logger.error(f"Audit producer failed for monitor {m.id}: {e}")
    finally:
        db.close()


@app.on_event("startup")
async def startup_tasks():
    # Run migration
    logger.info("Checking for database migrations...")
    try:
        from migrate_db import migrate

        migrate()
        logger.info("Database migration check finished.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

    # Start producer scheduler
    logger.info("Starting producer scheduler...")
    scheduler.add_job(_job, "interval", seconds=60)
    scheduler.add_job(
        _audit_job, "interval", hours=1
    )  # Run performance audit every hour
    scheduler.start()
