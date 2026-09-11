from sqlalchemy import String, DateTime, Integer, JSON, func, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.db.database import Base
from sqlalchemy import Index

class OutboxEvent(Base):
    """
    Outbox pattern event store.
    Events are inserted here in the same transaction as business data changes,
    then asynchronously published to a message broker (or processed by a worker).
    """
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        SQLEnum("pending", "processing", "completed", "failed", name="outbox_status"),
        default="pending",
        index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Retry/backoff bookkeeping for the ARQ poller (app/workers/arq_worker.py).
    # A failed publish attempt goes back to "pending" with next_attempt_at set
    # to an exponentially-delayed retry time, rather than straight to a
    # terminal "failed" — that only happens once retry_count reaches the
    # poller's attempt limit.
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
