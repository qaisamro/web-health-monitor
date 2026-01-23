import time
import asyncio
import httpx
import ssl
from typing import Optional
from sqlalchemy.orm import Session
from models import Monitor, CheckResult


async def check_one_url(
    url: str,
    timeout: float = 10.0,
    max_retries: int = 2,
    verify_ssl: bool = True
) -> dict:
    """
    فحص URL واحد مع دعم Retry و SSL verification.
    
    Args:
        url: الرابط المراد فحصه
        timeout: مهلة الاتصال بالثواني
        max_retries: عدد المحاولات عند الفشل
        verify_ssl: فحص شهادة SSL
    
    Returns:
        dict مع نتائج الفحص
    """
    attempts = 0
    last_error = None
    ssl_valid = None
    
    while attempts <= max_retries:
        attempts += 1
        start = time.perf_counter()
        
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                verify=verify_ssl
            ) as client:
                # استخدام HEAD أولاً (أسرع)، ثم GET إذا فشل
                try:
                    r = await client.head(url)
                except httpx.HTTPStatusError:
                    r = await client.get(url)
                
                ms = int((time.perf_counter() - start) * 1000)
                is_up = 200 <= r.status_code < 400
                
                # فحص SSL
                if url.startswith("https://"):
                    ssl_valid = True
                
                return {
                    "is_up": is_up,
                    "status_code": r.status_code,
                    "response_ms": ms,
                    "error": None,
                    "retry_attempts": attempts - 1,
                    "ssl_valid": ssl_valid
                }
                
        except ssl.SSLError as e:
            ssl_valid = False
            last_error = f"SSL Error: {str(e)}"
            
        except httpx.TimeoutException:
            last_error = f"Timeout after {timeout}s"
            
        except httpx.ConnectError as e:
            last_error = f"Connection Error: {str(e)}"
            
        except Exception as e:
            last_error = str(e)
        
        # انتظار قبل إعادة المحاولة (exponential backoff)
        if attempts <= max_retries:
            await asyncio.sleep(0.5 * attempts)
    
    ms = int((time.perf_counter() - start) * 1000)
    return {
        "is_up": False,
        "status_code": None,
        "response_ms": ms,
        "error": last_error,
        "retry_attempts": attempts - 1,
        "ssl_valid": ssl_valid
    }


async def check_multiple_urls(monitors: list[Monitor]) -> list[dict]:
    """
    فحص عدة مواقع بشكل متوازي (Concurrent).
    
    Args:
        monitors: قائمة الـ Monitors للفحص
    
    Returns:
        قائمة بنتائج الفحص
    """
    tasks = [
        check_one_url(
            url=m.url,
            timeout=float(m.timeout_seconds),
            max_retries=m.retry_count
        )
        for m in monitors
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # معالجة الأخطاء غير المتوقعة
    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed.append({
                "is_up": False,
                "status_code": None,
                "response_ms": 0,
                "error": f"Unexpected error: {str(result)}",
                "retry_attempts": 0,
                "ssl_valid": None
            })
        else:
            processed.append(result)
    
    return processed


async def run_checks(db: Session) -> int:
    """
    تشغيل الفحوصات لجميع المواقع النشطة بشكل متوازي.
    
    Args:
        db: جلسة قاعدة البيانات
    
    Returns:
        عدد المواقع التي تم فحصها
    """
    monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
    
    if not monitors:
        return 0
    
    # فحص متوازي لجميع المواقع
    results = await check_multiple_urls(monitors)
    
    # حفظ النتائج وتحديث الإحصائيات
    for monitor, result in zip(monitors, results):
        # إنشاء سجل النتيجة
        check_result = CheckResult(
            monitor_id=monitor.id,
            is_up=result["is_up"],
            status_code=result["status_code"],
            response_ms=result["response_ms"],
            error=result["error"],
            retry_attempts=result["retry_attempts"],
            ssl_valid=result["ssl_valid"]
        )
        db.add(check_result)
        
        # تحديث إحصائيات الـ Monitor
        monitor.update_stats(
            is_up=result["is_up"],
            response_ms=result["response_ms"]
        )
    
    db.commit()
    return len(monitors)


async def run_single_check(db: Session, monitor_id: int) -> Optional[dict]:
    """
    تشغيل فحص لموقع واحد محدد.
    
    Args:
        db: جلسة قاعدة البيانات
        monitor_id: معرف الـ Monitor
    
    Returns:
        نتيجة الفحص أو None إذا لم يوجد
    """
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    
    if not monitor:
        return None
    
    result = await check_one_url(
        url=monitor.url,
        timeout=float(monitor.timeout_seconds),
        max_retries=monitor.retry_count
    )
    
    # حفظ النتيجة
    check_result = CheckResult(
        monitor_id=monitor.id,
        is_up=result["is_up"],
        status_code=result["status_code"],
        response_ms=result["response_ms"],
        error=result["error"],
        retry_attempts=result["retry_attempts"],
        ssl_valid=result["ssl_valid"]
    )
    db.add(check_result)
    
    # تحديث الإحصائيات
    monitor.update_stats(
        is_up=result["is_up"],
        response_ms=result["response_ms"]
    )
    
    db.commit()
    return result
