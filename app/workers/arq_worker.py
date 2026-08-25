import asyncio
import os
from arq.connections import RedisSettings
from app.core.logger import logger
from app.db.database import SessionLocal
from app.models.outbox_event import OutboxEvent
from sqlalchemy import select, update

async def process_outbox_events_task(ctx):
    """
    Periodic task to process pending outbox events.
    """
    logger.info("Starting outbox event processing")
    
    # In a real async app we'd use async sqlalchemy. 
    # Since this app uses sync sqlalchemy, we must use a threadpool or run it in a sync way, 
    # but ARQ functions are async.
    # For now, we'll run it directly as this worker will block for DB operations.
    def _process():
        with SessionLocal() as db:
            events = db.execute(
                select(OutboxEvent).where(OutboxEvent.status == "pending").limit(50).with_for_update(skip_locked=True)
            ).scalars().all()
            
            for event in events:
                try:
                    logger.info(f"Publishing event {event.id} - topic: {event.topic}")
                    # Simulate publishing to Kafka/RabbitMQ
                    event.status = "completed"
                    event.processed_at = func.now()
                except Exception as e:
                    logger.error(f"Failed to process outbox event {event.id}: {e}")
                    event.status = "failed"
                    event.error_message = str(e)
            db.commit()

    # Run the sync DB code in an executor
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _process)
    logger.info("Finished outbox event processing")


async def send_email_task(ctx, to_email: str, subject: str, body: str):
    """
    Task to send an email asynchronously.
    """
    logger.info(f"Sending email to {to_email} - {subject}")
    # Simulate email sending delay
    await asyncio.sleep(1)
    logger.info(f"Email sent to {to_email}")
    return True


async def startup(ctx):
    logger.info("ARQ Worker starting...")

async def shutdown(ctx):
    logger.info("ARQ Worker shutting down...")

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Parse redis url to get host/port
# Extremely basic parsing for redis://host:port/db
host = "localhost"
port = 6379
database = 0
try:
    parts = redis_url.replace("redis://", "").split("/")
    host_port = parts[0].split(":")
    host = host_port[0]
    if len(host_port) > 1:
        port = int(host_port[1])
    if len(parts) > 1:
        database = int(parts[1])
except Exception:
    pass

class WorkerSettings:
    functions = [send_email_task]
    cron_jobs = [
        # In a real app we'd use arq cron to run process_outbox_events_task periodically
    ]
    redis_settings = RedisSettings(host=host, port=port, database=database)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
