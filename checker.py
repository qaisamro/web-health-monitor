import time
import httpx
import abc
import os
import asyncio
from typing import List, Optional
from logging_config import setup_logging

logger = setup_logging()

# -------------------- Strategy Pattern --------------------
class CheckStrategy(abc.ABC):
    @abc.abstractmethod
    async def check(self, url: str, **kwargs) -> dict:
        pass

class HTTPCheckStrategy(CheckStrategy):
    async def check(self, url: str, **kwargs) -> dict:
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                r = await client.get(url)
            ms = int((time.perf_counter() - start) * 1000)
            is_up = 200 <= r.status_code < 400
            return {"is_up": is_up, "status_code": r.status_code, "response_ms": ms, "error": None}
        except Exception as e:
            ms = int((time.perf_counter() - start) * 1000)
            return {"is_up": False, "status_code": None, "response_ms": ms, "error": str(e)}

class PerformanceAuditStrategy(CheckStrategy):
    async def check(self, url: str, strategy: str = "mobile") -> dict:
        target_url = url
        if not target_url.startswith("http"):
            target_url = "https://" + target_url
            
        api_key = os.getenv("GOOGLE_API_KEY")
        base_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {
            "url": target_url,
            "category": ["PERFORMANCE", "SEO", "ACCESSIBILITY", "BEST_PRACTICES"],
            "strategy": strategy
        }
        if api_key:
            params["key"] = api_key
            logger.info(f"Using API Key starting with: {api_key[:6]}...")
        else:
            logger.warning("No GOOGLE_API_KEY found, running without key (might be slow or limited)")
            
        max_retries = 3
        retry_delay = 5
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            for attempt in range(max_retries):
                try:
                    r = await client.get(base_url, params=params)
                    
                    if r.status_code == 200:
                        data = r.json()
                        lighthouse = data.get("lighthouseResult", {})
                        lh = data["lighthouseResult"]
                        audits = lh.get("audits", {})
                        
                        # Fetch Screenshot and Thumbnails
                        screenshot = audits.get("final-screenshot", {}).get("details", {}).get("data")
                        thumbnails = audits.get("screenshot-thumbnails", {}).get("details", {}).get("items", [])
                        
                        # Categories (Scores)
                        cats = lh.get("categories", {})
                        perf_score = cats.get("performance", {}).get("score", 0) * 100
                        seo_score = cats.get("seo", {}).get("score", 0) * 100
                        acc_score = cats.get("accessibility", {}).get("score", 0) * 100
                        bp_score = cats.get("best-practices", {}).get("score", 0) * 100
                        
                        # Fetch Core Web Vitals
                        fcp = audits.get("first-contentful-paint", {}).get("numericValue", 0) / 1000
                        lcp = audits.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000
                        cls = audits.get("cumulative-layout-shift", {}).get("numericValue", 0)
                        tbt = audits.get("total-blocking-time", {}).get("numericValue", 0)
                        
                        # Extract Top 10 failing audits
                        failing_audits = []
                        for audit_id, audit_data in audits.items():
                            if audit_data.get("score") is not None and audit_data.get("score") < 0.9:
                                failing_audits.append({
                                    "title": audit_data.get("title"),
                                    "description": audit_data.get("description"),
                                    "score": audit_data.get("score")
                                })
                        
                        logger.info(f"✅ PSI API Success for {url}")
                        return {
                            "perf_score": round(perf_score, 1),
                            "perf_seo": round(seo_score, 1),
                            "perf_accessible": round(acc_score, 1),
                            "perf_best_practices": round(bp_score, 1),
                            "perf_fcp": round(fcp, 2),
                            "perf_lcp": round(lcp, 2),
                            "perf_cls": round(cls, 3),
                            "perf_tbt": round(tbt, 0),
                            "perf_details": failing_audits[:10],
                            "perf_screenshot": screenshot,
                            "perf_thumbnails": thumbnails,
                            "error": None
                        }
                        
                    elif r.status_code == 429:
                        logger.warning(f"⚠️ PSI Rate Limit reached. Retrying in {retry_delay}s... (Attempt {attempt+1})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2 
                            continue
                        return {"error": "Google API Limit Reached (429). Please add an API Key."}
                    else:
                        error_msg = f"API Error {r.status_code}: {r.text[:200]}"
                        logger.error(f"❌ PSI {error_msg}")
                        return {"error": error_msg}
                        
                except Exception as e:
                    logger.error(f"⚠️ PSI Request failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return {"error": str(e)}
        return {"error": "Failed after max retries or unknown error"}

# You could easily add PingCheckStrategy here later...

# -------------------- Factory Pattern --------------------
class CheckStrategyFactory:
    @staticmethod
    def get_strategy(strategy_type: str = "http") -> CheckStrategy:
        if strategy_type == "http":
            return HTTPCheckStrategy()
        if strategy_type == "performance":
            return PerformanceAuditStrategy()
        raise ValueError(f"Unknown strategy type: {strategy_type}")

# -------------------- Observer Pattern (Alerting) --------------------
class Observer(abc.ABC):
    @abc.abstractmethod
    def update(self, monitor_name: str, result: dict):
        pass

class LogAlertObserver(Observer):
    def update(self, monitor_name: str, result: dict):
        if not result["is_up"]:
            print(f"🚨 ALERT: Monitor '{monitor_name}' is DOWN! Error: {result['error']}")

class HealthMonitorSubject:
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer: Observer):
        self._observers.append(observer)

    def notify(self, monitor_name: str, result: dict):
        for observer in self._observers:
            observer.update(monitor_name, result)

# Singleton instance of the alerting system
alert_system = HealthMonitorSubject()
alert_system.attach(LogAlertObserver())

# -------------------- Business Logic --------------------
async def run_check_on_monitor(monitor, strategy: CheckStrategy, **kwargs):
    result = await strategy.check(monitor.url, **kwargs)
    alert_system.notify(monitor.name, result)
    return result
