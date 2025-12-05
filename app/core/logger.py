import sys
import logging
from datetime import datetime
from pathlib import Path

import logging_loki
from loguru import logger

# Logs directory inside app/
log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

# Format for logs
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# Remove default handler to avoid duplicate logs
logger.remove()

# Console handler (colored logs)
logger.add(
    sys.stdout,
    format=LOG_FORMAT,
    level="INFO",
    colorize=True,
    enqueue=True,
    backtrace=True,
    diagnose=True,
)

# File handler (all logs)
logger.add(
    log_dir / f"{datetime.now().strftime('%Y-%m-%d')}-info.json",
    serialize=True,
    level="INFO",
    rotation="10 MB",
    retention="14 days",
    compression="zip",
    enqueue=True,
)

# Loki Handler
class LokiSink:
    def __init__(self, handler):
        self.handler = handler

    def write(self, message):
        record = message.record
        # Map loguru record to standard logging record
        log_record = logging.LogRecord(
            name=record["name"],
            level=logging.getLevelName(record["level"].name),
            pathname=record["file"].path,
            lineno=record["line"],
            msg=record["message"],
            args=(),
            exc_info=None,
        )
        self.handler.emit(log_record)

try:
    loki_handler = logging_loki.LokiHandler(
        url="http://loki:3100/loki/api/v1/push",
        tags={"job": "fastapi-app"},
        version="1",
    )
    logger.add(LokiSink(loki_handler), level="INFO")
except Exception as e:
    # Fallback if Loki is not available or lib is missing
    print(f"Failed to initialize Loki handler: {e}")

# Export the logger instance
__all__ = ["logger"]
