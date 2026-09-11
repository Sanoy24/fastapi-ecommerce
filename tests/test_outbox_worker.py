"""
Tests for the outbox event poller (app/workers/arq_worker.py).

process_outbox_events_task existed, correctly implemented, and was simply
never added to WorkerSettings — so no pending OutboxEvent row (written on
every order, see app/crud/order.py) was ever picked up. The whole table sat
at "pending" forever.

These tests exercise the task's actual DB session factory, not the app's
production one: app/db/database.py's SessionLocal is bound to
settings.Database_url, which points at a real long-lived database, not the
ephemeral PostgreSQL container this suite runs against (see conftest.py).
Every test here monkeypatches app.workers.arq_worker.SessionLocal — the name
as imported into that module — to a sessionmaker bound to the test
container's engine instead.
"""
import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.outbox_event import OutboxEvent
from app.workers.arq_worker import (
    MAX_OUTBOX_ATTEMPTS,
    OUTBOX_COMPLETED_RETENTION,
    WorkerSettings,
    _publish_event,
    cleanup_completed_outbox_events_task,
    process_outbox_events_task,
)


@pytest.fixture
def _use_test_db_for_worker(_engine, monkeypatch):
    """Point the worker's SessionLocal at the test container instead of
    the app's real database.
    """
    monkeypatch.setattr(
        "app.workers.arq_worker.SessionLocal", sessionmaker(bind=_engine)
    )


def _run(coro_fn):
    """Run an ARQ task coroutine to completion with a throwaway ctx dict."""
    asyncio.run(coro_fn({}))


class TestOutboxWorkerIsRegistered:
    """
    The actual bug: the task was written but never wired up. Everything
    else in this file tests behaviour that was already unreachable in
    production until this registration existed.
    """

    def test_process_outbox_events_task_is_registered(self):
        assert process_outbox_events_task in WorkerSettings.functions

    def test_cleanup_task_is_registered(self):
        assert cleanup_completed_outbox_events_task in WorkerSettings.functions

    def test_process_outbox_events_task_has_a_cron_schedule(self):
        scheduled = {job.coroutine for job in WorkerSettings.cron_jobs}
        assert process_outbox_events_task in scheduled

    def test_cleanup_task_has_a_cron_schedule(self):
        scheduled = {job.coroutine for job in WorkerSettings.cron_jobs}
        assert cleanup_completed_outbox_events_task in scheduled


class TestOutboxEventProcessing:
    def test_pending_event_is_marked_completed(
        self, db_session: Session, _use_test_db_for_worker
    ):
        event = OutboxEvent(topic="order.created", payload={"order_id": 1})
        db_session.add(event)
        db_session.commit()

        _run(process_outbox_events_task)

        db_session.expire_all()
        refreshed = db_session.get(OutboxEvent, event.id)
        assert refreshed.status == "completed"
        assert refreshed.processed_at is not None

    def test_already_completed_event_is_left_alone(
        self, db_session: Session, _use_test_db_for_worker
    ):
        event = OutboxEvent(
            topic="order.created",
            payload={"order_id": 1},
            status="completed",
            processed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(event)
        db_session.commit()
        original_processed_at = event.processed_at

        _run(process_outbox_events_task)

        db_session.expire_all()
        refreshed = db_session.get(OutboxEvent, event.id)
        assert refreshed.processed_at == original_processed_at

    def test_event_scheduled_for_the_future_is_not_picked_up_early(
        self, db_session: Session, _use_test_db_for_worker
    ):
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        event = OutboxEvent(
            topic="order.created",
            payload={},
            retry_count=1,
            next_attempt_at=future,
        )
        db_session.add(event)
        db_session.commit()

        _run(process_outbox_events_task)

        db_session.expire_all()
        refreshed = db_session.get(OutboxEvent, event.id)
        assert refreshed.status == "pending"


class TestOutboxRetryAndBackoff:
    """
    A failed publish must not strand an event: it goes back to "pending"
    with a backoff delay, and only becomes permanently "failed" after
    MAX_OUTBOX_ATTEMPTS.
    """

    def test_failed_publish_reschedules_with_backoff_instead_of_failing_immediately(
        self, db_session: Session, _use_test_db_for_worker, monkeypatch
    ):
        monkeypatch.setattr(
            "app.workers.arq_worker._publish_event",
            lambda event: (_ for _ in ()).throw(RuntimeError("broker unreachable")),
        )

        event = OutboxEvent(topic="order.created", payload={})
        db_session.add(event)
        db_session.commit()

        before = datetime.now(timezone.utc).replace(tzinfo=None)
        _run(process_outbox_events_task)

        db_session.expire_all()
        refreshed = db_session.get(OutboxEvent, event.id)
        assert refreshed.status == "pending", "one failure should not be terminal"
        assert refreshed.retry_count == 1
        assert refreshed.error_message and "broker unreachable" in refreshed.error_message
        assert refreshed.next_attempt_at is not None
        assert refreshed.next_attempt_at > before, "backoff must push the retry into the future"

    def test_event_is_not_retried_before_its_backoff_expires(
        self, db_session: Session, _use_test_db_for_worker, monkeypatch
    ):
        calls = []
        monkeypatch.setattr(
            "app.workers.arq_worker._publish_event",
            lambda event: calls.append(event.id) or (_ for _ in ()).throw(RuntimeError("down")),
        )

        event = OutboxEvent(topic="order.created", payload={})
        db_session.add(event)
        db_session.commit()

        _run(process_outbox_events_task)  # first failure, schedules a future retry
        assert len(calls) == 1

        _run(process_outbox_events_task)  # immediately again — backoff hasn't elapsed
        assert len(calls) == 1, "should not have retried before next_attempt_at"

    def test_event_fails_permanently_after_max_attempts(
        self, db_session: Session, _use_test_db_for_worker, monkeypatch
    ):
        monkeypatch.setattr(
            "app.workers.arq_worker._publish_event",
            lambda event: (_ for _ in ()).throw(RuntimeError("still down")),
        )

        event = OutboxEvent(topic="order.created", payload={})
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        for _ in range(MAX_OUTBOX_ATTEMPTS):
            # Simulate time passing so each poll actually picks the event
            # back up, rather than testing the backoff delay again here.
            db_session.execute(
                OutboxEvent.__table__.update()
                .where(OutboxEvent.id == event_id)
                .values(next_attempt_at=None)
            )
            db_session.commit()
            _run(process_outbox_events_task)

        db_session.expire_all()
        refreshed = db_session.get(OutboxEvent, event_id)
        assert refreshed.status == "failed"
        assert refreshed.retry_count == MAX_OUTBOX_ATTEMPTS
        assert refreshed.next_attempt_at is None


class TestOutboxCleanup:
    def test_old_completed_events_are_deleted(
        self, db_session: Session, _use_test_db_for_worker
    ):
        old_enough = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - OUTBOX_COMPLETED_RETENTION
            - timedelta(days=1)
        )
        old_event = OutboxEvent(
            topic="order.created", payload={}, status="completed", processed_at=old_enough
        )
        db_session.add(old_event)
        db_session.commit()
        old_id = old_event.id

        _run(cleanup_completed_outbox_events_task)

        db_session.expire_all()
        assert db_session.get(OutboxEvent, old_id) is None

    def test_recent_completed_events_are_kept(
        self, db_session: Session, _use_test_db_for_worker
    ):
        recent = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        recent_event = OutboxEvent(
            topic="order.created", payload={}, status="completed", processed_at=recent
        )
        db_session.add(recent_event)
        db_session.commit()
        recent_id = recent_event.id

        _run(cleanup_completed_outbox_events_task)

        db_session.expire_all()
        assert db_session.get(OutboxEvent, recent_id) is not None

    def test_old_pending_events_are_never_deleted(
        self, db_session: Session, _use_test_db_for_worker
    ):
        """Cleanup only ever removes "completed" rows — a pending or failed
        event, however old, is never silently discarded."""
        ancient = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=365)
        stuck_event = OutboxEvent(topic="order.created", payload={}, status="pending")
        db_session.add(stuck_event)
        db_session.commit()
        # Backdate created_at directly — the model defaults it to now().
        db_session.execute(
            OutboxEvent.__table__.update()
            .where(OutboxEvent.id == stuck_event.id)
            .values(created_at=ancient)
        )
        db_session.commit()
        stuck_id = stuck_event.id

        _run(cleanup_completed_outbox_events_task)

        db_session.expire_all()
        assert db_session.get(OutboxEvent, stuck_id) is not None


class TestOutboxSkipLockedConcurrency:
    """
    SQLite has no row-level locking, so `.with_for_update(skip_locked=True)`
    was previously untestable by construction. Now that the suite runs
    against a real PostgreSQL container (see conftest.py), this proves what
    skip_locked actually buys over a plain with_for_update(): a poller does
    not block waiting for rows a concurrent transaction is already holding —
    it works around them.
    """

    def test_poller_skips_rows_locked_by_another_open_transaction(
        self, db_session: Session, _engine, _use_test_db_for_worker
    ):
        events = [OutboxEvent(topic="order.created", payload={"i": i}) for i in range(6)]
        db_session.add_all(events)
        db_session.commit()
        all_ids = [e.id for e in events]
        locked_ids, free_ids = all_ids[:3], all_ids[3:]

        # A second, independent connection holds a real row lock on half the
        # events and deliberately does not commit — exactly what a second
        # poller instance's in-flight, uncommitted batch looks like to any
        # other concurrently-running poller.
        TestSessionLocal = sessionmaker(bind=_engine)
        holder = TestSessionLocal()
        holder.execute(
            select(OutboxEvent).where(OutboxEvent.id.in_(locked_ids)).with_for_update()
        ).scalars().all()

        try:
            started = time.monotonic()
            _run(process_outbox_events_task)
            elapsed = time.monotonic() - started
        finally:
            holder.rollback()
            holder.close()

        # A plain with_for_update() (no skip_locked) would block on the
        # held rows until `holder` released them above — i.e. until after
        # this call already returned. A generous bound well under "it
        # waited for the rollback in the finally block" is enough to show
        # it didn't block.
        assert elapsed < 5, (
            f"took {elapsed:.2f}s — looks like the poller blocked on rows "
            f"held by another transaction instead of skipping them"
        )

        db_session.expire_all()
        rows = {
            r.id: r.status
            for r in db_session.execute(
                select(OutboxEvent).where(OutboxEvent.id.in_(all_ids))
            ).scalars()
        }
        for locked_id in locked_ids:
            assert rows[locked_id] == "pending", (
                f"event {locked_id} was locked by another transaction — "
                f"skip_locked should have left it untouched, got {rows}"
            )
        for free_id in free_ids:
            assert rows[free_id] == "completed", (
                f"event {free_id} was never locked and should have been "
                f"processed in this same run, got {rows}"
            )

    def test_two_concurrent_pollers_each_publish_every_event_exactly_once(
        self, db_session: Session, _engine, _use_test_db_for_worker, monkeypatch
    ):
        """
        The correctness property skip_locked exists to protect: with two
        pollers running at once, every event is published exactly once —
        never zero times (it must still get done), never twice (that would
        mean the same order-confirmation email, refund webhook, etc. firing
        twice downstream).
        """
        publish_calls: list[int] = []
        lock = threading.Lock()

        def _tracking_publish(event):
            with lock:
                publish_calls.append(event.id)
            _publish_event(event)

        monkeypatch.setattr("app.workers.arq_worker._publish_event", _tracking_publish)

        events = [OutboxEvent(topic="order.created", payload={"i": i}) for i in range(20)]
        db_session.add_all(events)
        db_session.commit()
        event_ids = [e.id for e in events]

        barrier = threading.Barrier(2)

        def _poll():
            barrier.wait(timeout=5)
            _run(process_outbox_events_task)

        t_a = threading.Thread(target=_poll)
        t_b = threading.Thread(target=_poll)
        t_a.start()
        t_b.start()
        t_a.join(timeout=15)
        t_b.join(timeout=15)

        assert sorted(publish_calls) == sorted(set(publish_calls)), (
            f"an event was published more than once: {publish_calls}"
        )
        assert set(publish_calls) == set(event_ids), (
            "every event should have been published exactly once between "
            f"the two pollers; got {publish_calls}"
        )

        db_session.expire_all()
        statuses = {
            r.id: r.status
            for r in db_session.execute(
                select(OutboxEvent).where(OutboxEvent.id.in_(event_ids))
            ).scalars()
        }
        assert all(s == "completed" for s in statuses.values()), statuses
