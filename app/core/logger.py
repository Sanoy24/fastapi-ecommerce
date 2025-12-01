import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# Logs directory inside app/
log_dir = Path("logs")  # app/
# log_dir = BASE_DIR / "logs"
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
    level="INFO",  # change to INFO in prod
    colorize=True,
    enqueue=True,  # safe for async
    backtrace=True,  # show full traceback
    diagnose=True,  # detailed errors
)

# File handler (all logs)
logger.add(
    log_dir / f"{datetime.now().strftime('%Y-%m-%d')}-info.json",
    serialize=True,  # <--- IMPORTANT: turn logs into JSON
    level="INFO",
    rotation="10 MB",
    retention="14 days",
    compression="zip",
    enqueue=True,
)

# File handler (only errors)
# logger.add(
#     log_dir / f"{datetime.now().strftime('%Y-%m-%d')}-errors.log",
#     format=LOG_FORMAT,
#     level="ERROR",
#     rotation="5 MB",
#     retention="30 days",
#     compression="zip",
#     enqueue=True,
# )

# Export the logger instance
__all__ = ["logger"]
__all__ = ["logger"]
