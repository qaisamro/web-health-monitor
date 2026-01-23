import time
import httpx
from sqlalchemy.orm import Session
from models import Monitor, CheckResult
from logging_config import setup_logging

logger = setup_logging("checker")


async def check_one_url(url: str) -> dict:
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            r = await client.get(url)
        ms = int((time.perf_counter() - start) * 1000)
        is_up = 200 <= r.status_code < 400
        return {"is_up": is_up, "status_code": r.status_code, "response_ms": ms, "error": None}
    except Exception as e:
        ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"Error checking {url}: {e}")
        return {"is_up": False, "status_code": None, "response_ms": ms, "error": str(e)}


async def run_checks(db: Session) -> int:
    """Runs checks for all active monitors once. Returns how many monitors were checked."""
    monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
    for m in monitors:
        result = await check_one_url(m.url)
        db.add(
            CheckResult(
                monitor_id=m.id,
                is_up=result["is_up"],
                status_code=result["status_code"],
                response_ms=result["response_ms"],
                error=result["error"],
            )
        )
        status = "UP" if result["is_up"] else "DOWN"
        logger.info(f"Checked {m.url}: {status} ({result['response_ms']}ms)")
    db.commit()
    return len(monitors)
