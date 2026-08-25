from sqlalchemy import String, DateTime, JSON, func, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.db.database import Base

class OutboxEvent(Base):
    """
    Outbox pattern event store.
    Events are inserted here in the same transaction as business data changes,
    then asynchronously published to a message broker (or processed by a worker).
    """
    __tablename__ = "outbox_events"

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
