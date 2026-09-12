import asyncio
import os
from datetime import timedelta
from arq.connections import RedisSettings
from arq.cron import cron
from app.core.logger import logger
from app.db.database import SessionLocal
from app.models.outbox_event import OutboxEvent
from app.utils.time import utcnow
from sqlalchemy import select, func, delete

# Previously this function existed but was never added to WorkerSettings
# below, so no pending OutboxEvent row was ever processed — every order
# wrote one and it sat at "pending" forever. Registering it is the fix;
# everything else here (retry/backoff, cleanup) is what makes that
# registration actually safe to leave running unattended.

# After this many failed publish attempts, an event is given up on and
# marked "failed" for good instead of being retried again.
MAX_OUTBOX_ATTEMPTS = 5

# Completed events are the durable record that a publish happened; once
# they're old enough to be uninteresting for debugging, `_cleanup` removes
# them so the table doesn't grow forever holding rows nothing reads anymore.
OUTBOX_COMPLETED_RETENTION = timedelta(days=30)


def _backoff_delay(attempt: int) -> timedelta:
    """Exponential backoff: 2, 4, 8, 16, 32 minutes, capped at 1 hour."""
    return timedelta(minutes=min(2**attempt, 60))


def _publish_event(event: OutboxEvent) -> None:
    """
    Publish one outbox event to the downstream broker.

    This app has no message broker wired up, so publishing is simulated by
    logging — this is the one function to swap out for a real client
    (Kafka, RabbitMQ, SNS, ...) when one exists. The retry/backoff
    bookkeeping in process_outbox_events_task doesn't need to change when
    that happens; it only depends on this function raising on failure.
    """
    logger.info(f"Publishing event {event.id} - topic: {event.topic}")


async def process_outbox_events_task(ctx):
    """
    Periodic task to process pending outbox events.

    A failure doesn't immediately give up: the event goes back to "pending"
    with next_attempt_at pushed out by an exponential backoff, and is only
    marked terminally "failed" after MAX_OUTBOX_ATTEMPTS. Without this, a
    single transient failure (a broker hiccup, a network blip) would strand
    an event with no automatic path back to being processed.

    "product.back_in_stock" events actually send an email once
    successfully "published" (see below) — every other topic just logs,
    same as before, since there's still no real broker to hand off to.
    """
    logger.info("Starting outbox event processing")

    # In a real async app we'd use async sqlalchemy.
    # Since this app uses sync sqlalchemy, we must use a threadpool or run it in a sync way,
    # but ARQ functions are async.
    # For now, we'll run it directly as this worker will block for DB operations.
    def _process():
        now = utcnow()
        back_in_stock_payloads = []
        with SessionLocal() as db:
            events = (
                db.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.status == "pending",
                        (OutboxEvent.next_attempt_at.is_(None))
                        | (OutboxEvent.next_attempt_at <= now),
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(50)
                    # skip_locked lets multiple worker instances poll the
                    # same table concurrently without either blocking on or
                    # double-processing a row another worker already picked
                    # up — the reason this suite now runs on real
                    # PostgreSQL rather than SQLite is to be able to prove
                    # that guarantee actually holds (see
                    # tests/test_outbox_worker.py).
                    .with_for_update(skip_locked=True)
                )
                .scalars()
                .all()
            )

            for event in events:
                try:
                    _publish_event(event)
                    event.status = "completed"
                    event.processed_at = func.now()
                    if event.topic == "product.back_in_stock":
                        back_in_stock_payloads.append(dict(event.payload))
                except Exception as e:
                    event.retry_count += 1
                    if event.retry_count >= MAX_OUTBOX_ATTEMPTS:
                        logger.error(
                            f"Outbox event {event.id} failed permanently after "
                            f"{event.retry_count} attempts: {e}"
                        )
                        event.status = "failed"
                        event.next_attempt_at = None
                    else:
                        delay = _backoff_delay(event.retry_count)
                        logger.warning(
                            f"Outbox event {event.id} failed (attempt "
                            f"{event.retry_count}/{MAX_OUTBOX_ATTEMPTS}), retrying "
                            f"in {delay}: {e}"
                        )
                        event.next_attempt_at = now + delay
                    event.error_message = str(e)
            db.commit()
        return back_in_stock_payloads

    # Run the sync DB code in an executor
    loop = asyncio.get_running_loop()
    back_in_stock_payloads = await loop.run_in_executor(None, _process)

    if back_in_stock_payloads:
        from app.services.email_service import send_back_in_stock_email

        for payload in back_in_stock_payloads:
            await send_back_in_stock_email(
                to_address=payload["email"],
                product_name=payload["product_name"],
                product_slug=payload["product_slug"],
            )

    logger.info("Finished outbox event processing")


async def cleanup_completed_outbox_events_task(ctx):
    """Delete completed outbox events older than the retention window."""
    logger.info("Starting outbox cleanup")

    def _process():
        cutoff = utcnow() - OUTBOX_COMPLETED_RETENTION
        with SessionLocal() as db:
            result = db.execute(
                delete(OutboxEvent).where(
                    OutboxEvent.status == "completed",
                    OutboxEvent.processed_at < cutoff,
                )
            )
            db.commit()
            return result.rowcount

    loop = asyncio.get_running_loop()
    deleted = await loop.run_in_executor(None, _process)
    logger.info(f"Finished outbox cleanup — removed {deleted} completed event(s)")


async def send_order_confirmation_email_task(
    ctx, to_address: str, order_number: str, total_amount: float
):
    from app.services.email_service import send_order_confirmation_email

    logger.info(f"ARQ: Sending order confirmation to {to_address}")
    await send_order_confirmation_email(to_address, order_number, total_amount)
    return True


async def send_password_reset_email_task(ctx, to_address: str, reset_token: str):
    from app.services.email_service import send_password_reset_email

    logger.info(f"ARQ: Sending password reset to {to_address}")
    await send_password_reset_email(to_address, reset_token)
    return True


async def send_verification_email_task(ctx, to_address: str, verification_token: str):
    from app.services.email_service import send_verification_email

    logger.info(f"ARQ: Sending verification email to {to_address}")
    await send_verification_email(to_address, verification_token)
    return True


async def send_guest_order_claim_email_task(ctx, to_address: str, order_number: str, claim_token: str):
    from app.services.email_service import send_guest_order_claim_email

    logger.info(f"ARQ: Sending guest order claim link for order {order_number} to {to_address}")
    await send_guest_order_claim_email(to_address, order_number, claim_token)
    return True


async def detect_abandoned_carts_task(ctx):
    """
    Find carts with items where last_activity_at < NOW() - 24h and user has
    email, and send a recovery email.

    Cart.abandoned_email_sent_at is what makes this safe to run twice a
    day forever: a cart is only picked up if it's never been notified, or
    its last_activity_at has moved past the last notification — i.e. the
    customer touched it again since. Without that check, this cron would
    re-email the same still-abandoned cart on every single run.
    """
    logger.info("Starting abandoned cart detection")

    def _process():
        from app.models.cart import Cart
        from app.models.user import User

        now = utcnow()
        cutoff = now - timedelta(hours=24)

        with SessionLocal() as db:
            carts = (
                db.execute(
                    select(Cart)
                    .join(User)
                    .where(Cart.last_activity_at < cutoff)
                    .where(Cart.user_id.isnot(None))
                    .where(
                        (Cart.abandoned_email_sent_at.is_(None))
                        | (Cart.abandoned_email_sent_at < Cart.last_activity_at)
                    )
                    .limit(100)
                )
                .scalars()
                .all()
            )

            to_notify = []
            for cart in carts:
                if cart.cart_items and cart.user:
                    to_notify.append((cart.user.email, len(cart.cart_items)))
                    # Marked before the email actually sends: this batch
                    # won't be picked up again on the next run regardless
                    # of whether the send below succeeds, matching the
                    # "at most one reminder per abandonment" intent rather
                    # than risking a stuck cart re-triggering endlessly if
                    # send_abandoned_cart_email starts failing.
                    cart.abandoned_email_sent_at = now

            db.commit()
            return to_notify

    loop = asyncio.get_running_loop()
    to_notify = await loop.run_in_executor(None, _process)

    from app.services.email_service import send_abandoned_cart_email

    for email, item_count in to_notify:
        logger.info(f"Sending abandoned-cart email to {email} ({item_count} item(s))")
        await send_abandoned_cart_email(to_address=email, item_count=item_count)

    logger.info(f"Finished abandoned cart detection — notified {len(to_notify)} cart(s)")


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
        send_guest_order_claim_email_task,
        detect_abandoned_carts_task,
        process_outbox_events_task,
        cleanup_completed_outbox_events_task,
    ]

    cron_jobs = [
        cron(detect_abandoned_carts_task, hour={0, 12}, minute=0),  # run twice a day
        # Twice a minute: the outbox pattern's whole point is a business
        # transaction and its side effect committing together, so the
        # side effect (here, simulated) should follow close behind.
        cron(process_outbox_events_task, second={0, 30}),
        cron(cleanup_completed_outbox_events_task, hour=3, minute=0),  # once a day
    ]
    redis_settings = RedisSettings(host=host, port=port, database=database)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
