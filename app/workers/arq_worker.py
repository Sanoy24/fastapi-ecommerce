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


from app.services.email_service import (
    send_order_confirmation_email,
    send_password_reset_email,
    send_verification_email,
)

async def send_order_confirmation_email_task(ctx, to_address: str, order_number: str, total_amount: float):
    logger.info(f"ARQ: Sending order confirmation to {to_address}")
    await send_order_confirmation_email(to_address, order_number, total_amount)
    return True

async def send_password_reset_email_task(ctx, to_address: str, reset_token: str):
    logger.info(f"ARQ: Sending password reset to {to_address}")
    await send_password_reset_email(to_address, reset_token)
    return True

async def send_verification_email_task(ctx, to_address: str, verification_token: str):
    logger.info(f"ARQ: Sending verification email to {to_address}")
    await send_verification_email(to_address, verification_token)
    return True


async def detect_abandoned_carts_task(ctx):
    """
    Find carts with items where last_activity_at < NOW() - 24h and user has email, enqueue recovery emails.
    """
    logger.info("Starting abandoned cart detection")
    
    def _process():
        from app.models.cart import Cart
        from app.models.user import User
        import datetime
        
        cutoff = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=24)
        
        with SessionLocal() as db:
            # find carts with activity older than 24h, having items, and a user with email
            carts = db.execute(
                select(Cart)
                .join(User)
                .where(Cart.last_activity_at < cutoff)
                .where(Cart.user_id.isnot(None))
                # Note: In a production app, we would add a flag to track if we already sent the email
                .limit(100) 
            ).scalars().all()
            
            for cart in carts:
                if cart.cart_items and cart.user:
                    logger.info(f"Abandoned cart detected for user {cart.user.email}")
                    # Simulate enqueueing email
                    # await ctx['redis'].enqueue_job('send_abandoned_cart_email_task', cart.user.email, cart.id)
                    pass
                    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _process)
    logger.info("Finished abandoned cart detection")
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
    functions = [
        send_order_confirmation_email_task,
        send_password_reset_email_task,
        send_verification_email_task,
        detect_abandoned_carts_task,
    ]
    
    from arq.cron import cron
    cron_jobs = [
        cron(detect_abandoned_carts_task, hour={0, 12}, minute=0) # run twice a day
    ]
    redis_settings = RedisSettings(host=host, port=port, database=database)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
