from sqlalchemy import Integer, String, ForeignKey, Numeric, DateTime
from typing import Optional
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import JSON
from app.db.database import Base


class Payment(Base):
    """Payment entity tracking payment method, status, and transaction info."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        SQLEnum(
            "credit_card", "paypal", "bank_transfer", "stripe", name="payment_method"
        ),
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        SQLEnum("pending", "completed", "failed", name="payment_transaction_status"),
        default="pending",
    )
    transaction_id: Mapped[str] = mapped_column(String(100))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    refund_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="payments")
