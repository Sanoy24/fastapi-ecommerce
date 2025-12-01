from sqlalchemy import Integer, ForeignKey, Numeric, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLEnum
from typing import List
from datetime import datetime
from app.db.database import Base


class Order(Base):
    """Order entity representing a customer's purchase and fulfillment state."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    shipping_address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    billing_address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        SQLEnum(
            "pending", "paid", "shipped", "delivered", "cancelled", name="order_status"
        ),
        default="pending",
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    shipped_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    tx_ref: Mapped[str] = mapped_column(String(255), unique=True)
    payment_status: Mapped[str] = mapped_column(
        SQLEnum("pending", "success", "failed", name="payment_status"),
        default="pending",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    shipping_address: Mapped["Address"] = relationship(
        "Address", foreign_keys=[shipping_address_id]
    )
    billing_address: Mapped["Address"] = relationship(
        "Address", foreign_keys=[billing_address_id]
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment", back_populates="order", cascade="all, delete-orphan"
    )
