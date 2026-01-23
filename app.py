from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

from db import Base, engine, SessionLocal, cleanup_old_results
from models import Monitor, CheckResult
from checker import run_checks, run_single_check

app = FastAPI(title="Web Health Monitor (Improved)")
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
    return templates.TemplateResponse("index.html", {"request": request})


# -------------------- Schemas --------------------
class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    url: HttpUrl
    interval_seconds: int = Field(60, ge=10, le=3600)
    timeout_seconds: int = Field(10, ge=1, le=60)
    retry_count: int = Field(2, ge=0, le=5)


class MonitorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    url: HttpUrl | None = None
    interval_seconds: int | None = Field(None, ge=10, le=3600)
    is_active: bool | None = None
    timeout_seconds: int | None = Field(None, ge=1, le=60)
    retry_count: int | None = Field(None, ge=0, le=5)


# -------------------- API - Monitors --------------------
@app.post("/monitors")
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    m = Monitor(
        name=payload.name,
        url=str(payload.url),
        interval_seconds=payload.interval_seconds,
        timeout_seconds=payload.timeout_seconds,
        retry_count=payload.retry_count,
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
        "timeout_seconds": m.timeout_seconds,
        "retry_count": m.retry_count,
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
            "timeout_seconds": m.timeout_seconds,
            "retry_count": m.retry_count,
            "is_active": m.is_active,
            "last_status": m.last_status,
            "last_check_at": m.last_check_at,
            "uptime_percentage": m.uptime_percentage,
            "avg_response_ms": m.avg_response_ms,
            "total_checks": m.total_checks,
        }
        for m in monitors
    ]


@app.get("/monitors/{monitor_id}")
def get_monitor(monitor_id: int, db: Session = Depends(get_db)):
    m = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return {
        "id": m.id,
        "name": m.name,
        "url": m.url,
        "interval_seconds": m.interval_seconds,
        "timeout_seconds": m.timeout_seconds,
        "retry_count": m.retry_count,
        "is_active": m.is_active,
        "last_status": m.last_status,
        "last_check_at": m.last_check_at,
        "uptime_percentage": m.uptime_percentage,
        "avg_response_ms": m.avg_response_ms,
        "total_checks": m.total_checks,
        "successful_checks": m.successful_checks,
        "created_at": m.created_at,
    }


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
    if payload.timeout_seconds is not None:
        m.timeout_seconds = payload.timeout_seconds
    if payload.retry_count is not None:
        m.retry_count = payload.retry_count

    db.commit()
    db.refresh(m)
    return {
        "id": m.id,
        "name": m.name,
        "url": m.url,
        "interval_seconds": m.interval_seconds,
        "timeout_seconds": m.timeout_seconds,
        "retry_count": m.retry_count,
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


# -------------------- API - Check Results --------------------
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
        "retry_attempts": last.retry_attempts,
        "ssl_valid": last.ssl_valid,
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
            "retry_attempts": r.retry_attempts,
            "ssl_valid": r.ssl_valid,
        }
        for r in rows
    ]


# -------------------- API - Statistics --------------------
@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """إحصائيات عامة للنظام."""
    total_monitors = db.query(Monitor).count()
    active_monitors = db.query(Monitor).filter(Monitor.is_active == True).count()
    total_checks = db.query(CheckResult).count()
    
    # حساب متوسط uptime
    monitors = db.query(Monitor).all()
    avg_uptime = 0.0
    if monitors:
        avg_uptime = sum(m.uptime_percentage or 0 for m in monitors) / len(monitors)
    
    # عدد المواقع المعطلة حالياً
    down_monitors = db.query(Monitor).filter(
        Monitor.is_active == True,
        Monitor.last_status == False
    ).count()
    
    return {
        "total_monitors": total_monitors,
        "active_monitors": active_monitors,
        "down_monitors": down_monitors,
        "total_checks": total_checks,
        "average_uptime": round(avg_uptime, 2),
    }


@app.get("/monitors/{monitor_id}/stats")
def get_monitor_stats(monitor_id: int, db: Session = Depends(get_db)):
    """إحصائيات تفصيلية لموقع محدد."""
    m = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    # آخر 10 فحوصات
    recent_checks = (
        db.query(CheckResult)
        .filter(CheckResult.monitor_id == monitor_id)
        .order_by(CheckResult.checked_at.desc())
        .limit(10)
        .all()
    )
    
    return {
        "monitor_id": monitor_id,
        "name": m.name,
        "uptime_percentage": m.uptime_percentage,
        "avg_response_ms": m.avg_response_ms,
        "total_checks": m.total_checks,
        "successful_checks": m.successful_checks,
        "failed_checks": m.total_checks - m.successful_checks,
        "last_status": m.last_status,
        "last_check_at": m.last_check_at,
        "recent_checks": [
            {
                "checked_at": c.checked_at,
                "is_up": c.is_up,
                "response_ms": c.response_ms,
            }
            for c in recent_checks
        ],
    }


# -------------------- API - Actions --------------------
@app.post("/run-once")
async def run_once():
    """تشغيل فحص واحد لجميع المواقع النشطة."""
    db = SessionLocal()
    try:
        n = await run_checks(db)
        return {"ok": True, "checked": n}
    finally:
        db.close()


@app.post("/monitors/{monitor_id}/check")
async def check_single_monitor(monitor_id: int):
    """تشغيل فحص لموقع واحد محدد."""
    db = SessionLocal()
    try:
        result = await run_single_check(db, monitor_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Monitor not found")
        return {"ok": True, "result": result}
    finally:
        db.close()


@app.post("/cleanup")
def cleanup_old_data(days: int = 30, db: Session = Depends(get_db)):
    """حذف البيانات القديمة."""
    deleted = cleanup_old_results(db, days=days)
    return {"ok": True, "deleted_records": deleted}


# -------------------- Scheduler --------------------
scheduler = AsyncIOScheduler()


async def _job():
    db = SessionLocal()
    try:
        await run_checks(db)
    finally:
        db.close()


async def _cleanup_job():
    """تنظيف دوري للبيانات القديمة (كل 24 ساعة)."""
    db = SessionLocal()
    try:
        cleanup_old_results(db, days=30)
    finally:
        db.close()


@app.on_event("startup")
def start_scheduler():
    # فحص دوري كل 60 ثانية
    scheduler.add_job(lambda: asyncio.create_task(_job()), "interval", seconds=60)
    # تنظيف دوري كل 24 ساعة
    scheduler.add_job(lambda: asyncio.create_task(_cleanup_job()), "interval", hours=24)
    scheduler.start()
