import logging
import sys
import json
import os
from datetime import datetime


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "process": record.process,
            "thread": record.threadName,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger()

    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JsonFormatter())
    logger.addHandler(console_handler)

    # File handler for persistent logging (structured)
    log_dir = os.path.dirname(
        os.getenv("DATABASE_URL", "/app/data/").replace("sqlite:///", "")
    )
    if log_dir and os.path.exists(log_dir):
        file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"))
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

    return logger
