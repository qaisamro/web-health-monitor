import pika
import json
import asyncio
import os
import sys
import time
import httpx
from circuitbreaker import circuit
from sqlalchemy.orm import Session

from db import SessionLocal
from models import Monitor, CheckResult
from checker import CheckStrategyFactory, run_check_on_monitor
from logging_config import setup_logging

logger = setup_logging()
logger.info("--- WORKER v2.3.1 STARTING ---")

# Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QUEUE_NAME = "health_checks"

# -------------------- Resilience: Circuit Breaker --------------------
# Create a strategy using the factory
strategy_factory = CheckStrategyFactory()
http_strategy = strategy_factory.get_strategy("http")
perf_strategy = strategy_factory.get_strategy("performance")


@circuit(failure_threshold=5, recovery_timeout=60)
async def resilient_check(monitor):
    return await run_check_on_monitor(monitor, http_strategy)


async def process_audit(monitor_id: int, strategy: str = "mobile"):
    logger.info(f"🔍 [Worker] process_audit called for ID {monitor_id}")
    db = SessionLocal()
    monitor = None
    try:
        logger.info(f"🔍 [Worker] Fetching monitor {monitor_id} from DB...")
        monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
        if not monitor:
            logger.warning(f"⚠️ [Worker] Monitor {monitor_id} not found in DB.")
            return

        logger.info(
            f"🚀 [Worker] Starting Performance Audit ({strategy}) for {monitor.url}"
        )
        result = await perf_strategy.check(monitor.url, strategy=strategy)
        logger.info(f"🔍 [Worker] PSI Check returned for {monitor.url}")

        if not result.get("error"):
            monitor.perf_score = result["perf_score"]
            monitor.perf_seo = result["perf_seo"]
            monitor.perf_accessible = result["perf_accessible"]
            monitor.perf_best_practices = result["perf_best_practices"]
            monitor.perf_fcp = result["perf_fcp"]
            monitor.perf_lcp = result["perf_lcp"]
            monitor.perf_cls = result["perf_cls"]
            monitor.perf_tbt = result["perf_tbt"]
            monitor.perf_details = result["perf_details"]
            monitor.perf_screenshot = result["perf_screenshot"]
            monitor.perf_thumbnails = result.get("perf_thumbnails")
            db.commit()
            logger.info(
                f"✅ Audit Complete for {monitor.url}: Score {result['perf_score']}"
            )

            # Broadcast update via API internal endpoint
            try:
                api_base = os.getenv("API_URL", "http://api:8000")
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{api_base}/api/v1/internal/broadcast",
                        json={"event": "audit_finished", "monitor_id": monitor.id},
                        timeout=5.0,
                    )
            except Exception as e:
                logger.error(f"Failed to notify API: {e}")
        else:
            raise Exception(result["error"])

    except Exception as e:
        logger.error(f"❌ Audit Failed for {monitor_id}: {e}")
        if monitor:
            # Notify UI about failure
            try:
                api_base = os.getenv("API_URL", "http://api:8000")
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{api_base}/api/v1/internal/broadcast",
                        json={
                            "event": "audit_failed",
                            "monitor_id": monitor.id,
                            "error": str(e),
                        },
                        timeout=5.0,
                    )
            except:
                pass
    finally:
        db.close()


async def process_check(monitor_id: int):
    db = SessionLocal()
    try:
        monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
        if not monitor:
            logger.warning(f"Monitor {monitor_id} not found.")
            return

        logger.info(f"Processing check for {monitor.url} (ID: {monitor_id})")

        try:
            result = await resilient_check(monitor)

            # Save result
            db.add(
                CheckResult(
                    monitor_id=monitor.id,
                    is_up=result["is_up"],
                    status_code=result["status_code"],
                    response_ms=result["response_ms"],
                    error=result["error"],
                )
            )
            db.commit()

            status = "UP" if result["is_up"] else "DOWN"
            logger.info(
                f"Result for {monitor.url}: {status} ({result['response_ms']}ms)"
            )

            # Broadcast instant update via API
            try:
                api_base = os.getenv("API_URL", "http://api:8000")
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{api_base}/api/v1/internal/broadcast",
                        json={
                            "event": "check_finished",
                            "monitor_id": monitor.id,
                            "is_up": result["is_up"],
                        },
                        timeout=2.0,
                    )
            except:
                pass

        except Exception as e:
            # This catches CircuitBreaker errors or other execution flows
            logger.error(f"Execution failed for {monitor.url}: {e}")

    finally:
        db.close()


def callback(ch, method, properties, body):
    try:
        msg = body.decode()
        logger.info(f"📥 Received task: {msg}")
        data = json.loads(msg)
        monitor_id = data.get("monitor_id")
        task_type = data.get("task_type", "check")
        strategy = data.get("strategy", "mobile")

        if monitor_id:
            if task_type == "audit":
                asyncio.run(process_audit(monitor_id, strategy=strategy))
            else:
                asyncio.run(process_check(monitor_id))
    except Exception as e:
        logger.error(f"Error in callback: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    logger.info(f"Worker starting, connecting to RabbitMQ at {RABBITMQ_HOST}...")
    import traceback

    retries = 5
    while retries > 0:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST, connection_attempts=3, retry_delay=5
                )
            )
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

            logger.info("Worker ready and waiting for messages. To exit press CTRL+C")
            channel.start_consuming()
            break
        except Exception as e:
            logger.error(f"Critical Worker Error: {str(e)}")
            logger.error(traceback.format_exc())
            retries -= 1
            if retries > 0:
                logger.info(
                    f"Retrying connection in 5 seconds... ({retries} attempts left)"
                )
                time.sleep(5)
            else:
                logger.error("Max retries reached. Exiting.")
                sys.exit(1)


if __name__ == "__main__":
    main()
