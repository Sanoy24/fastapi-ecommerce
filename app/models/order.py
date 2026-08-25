from sqlalchemy import ForeignKey, Numeric, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLEnum
from typing import List, Optional
from datetime import datetime
from app.db.database import Base
from sqlalchemy import JSON, Index


class Order(Base):
    """Order entity representing a customer's purchase and fulfillment state."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id_status", "user_id", "status"),
    )

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
    coupon_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        SQLEnum(
            "pending", "paid", "processing", "packed", "shipped", "delivered", "cancelled",
            "payment_failed", "refund_pending", "refunded", "return_requested", "return_approved",
            name="order_status"
        ),
        default="pending",
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_carrier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tx_ref: Mapped[str] = mapped_column(String(255), unique=True)
    payment_status: Mapped[str] = mapped_column(
        SQLEnum("pending", "success", "failed", name="payment_status"),
        default="pending",
    )

    # New fields for order snapshots
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    shipping_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    shipping_address_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    billing_address_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    coupon: Mapped[Optional["Coupon"]] = relationship("Coupon", back_populates="orders")
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
    events: Mapped[List["OrderEvent"]] = relationship(
        "OrderEvent", back_populates="order", cascade="all, delete-orphan", order_by="OrderEvent.created_at.desc()"
    )
    shipments = relationship("Shipment", back_populates="order")
