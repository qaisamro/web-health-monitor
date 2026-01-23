from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

from db import Base, engine, SessionLocal
from models import Monitor, CheckResult
from checker import run_checks

app = FastAPI(title="Web Health Monitor (MVP + Dashboard)")
templates = Jinja2Templates(directory="templates")

# Create tables
Base.metadata.create_all(bind=engine)


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


# -------------------- API --------------------
@app.post("/monitors")
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
    return {
        "id": m.id,
        "name": m.name,
        "url": m.url,
        "interval_seconds": m.interval_seconds,
        "is_active": m.is_active,
    }


@app.get("/monitors")
def list_monitors(db: Session = Depends(get_db)):
    monitors = db.query(Monitor).order_by(Monitor.id.asc()).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "url": m.url,
            "interval_seconds": m.interval_seconds,
            "is_active": m.is_active,
        }
        for m in monitors
    ]


@app.patch("/monitors/{monitor_id}")
def update_monitor(monitor_id: int, payload: MonitorUpdate, db: Session = Depends(get_db)):
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


@app.delete("/monitors/{monitor_id}")
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    m = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")
    db.delete(m)
    db.commit()
    return {"ok": True}


@app.get("/monitors/{monitor_id}/latest")
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


@app.get("/monitors/{monitor_id}/checks")
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


@app.post("/run-once")
async def run_once():
    """Manually trigger checks once (useful for demo without waiting a full minute)."""
    db = SessionLocal()
    try:
        n = await run_checks(db)
        return {"ok": True, "checked": n}
    finally:
        db.close()


# -------------------- Scheduler --------------------
scheduler = AsyncIOScheduler()


async def _job():
    db = SessionLocal()
    try:
        await run_checks(db)
    finally:
        db.close()


@app.on_event("startup")
def start_scheduler():
    # Fixed interval job (every 60 seconds) for MVP
    scheduler.add_job(lambda: asyncio.create_task(_job()), "interval", seconds=60)
    scheduler.start()
