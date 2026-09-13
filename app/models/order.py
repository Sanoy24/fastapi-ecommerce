from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, DateTime, func
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
        Index("ix_orders_guest_email", "guest_email"),
        CheckConstraint(
            "user_id IS NOT NULL OR guest_email IS NOT NULL",
            name="ck_orders_user_or_guest_email",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Nullable: a guest checkout order has no user_id at all — see
    # guest_email below and app/crud/order.py create_guest_order. The check
    # constraint guarantees every order is attributable to someone one way
    # or the other.
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    # Set only for guest orders. Kept permanently even after the order is
    # later claimed into an account (see OrderService.claim_guest_order) —
    # it's a historical record of who originally placed the order, not a
    # live ownership pointer.
    guest_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Nullable: a guest has no Address row to point at — the snapshot
    # columns below are the source of truth for a guest order's address,
    # built directly from the inline address the guest submitted at
    # checkout rather than from a loaded Address.
    shipping_address_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=True
    )
    billing_address_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=True
    )
    coupon_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # total_amount and every other monetary column on this model stay in
    # settings.BASE_CURRENCY_CODE always, regardless of what currency_code
    # says below — that's what keeps SUM(total_amount) in admin analytics
    # meaningful across every order ever placed. currency_code +
    # exchange_rate_at_purchase record what the customer actually saw and
    # was charged (see PaymentService._create_payment_intent_for_order,
    # which converts total_amount * exchange_rate_at_purchase into the
    # real Stripe charge); exchange_rate_at_purchase is snapshotted here
    # rather than read live from Currency so a later rate change never
    # rewrites what a past order was actually billed.
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )
    exchange_rate_at_purchase: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=1)
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

    # Loyalty points spent as a discount on this order (deducted from the
    # user's balance at checkout — see OrderCrud._calculate_discount) and
    # points credited once payment succeeds (0 until then, and always 0 for
    # a guest order — see PaymentService._handle_successful_payment). Both
    # are snapshotted here, not just on User, so refund/cancellation can
    # reverse exactly what this order did without recomputing it later.
    points_redeemed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="orders")
    coupon: Mapped[Optional["Coupon"]] = relationship("Coupon", back_populates="orders")
    shipping_address: Mapped[Optional["Address"]] = relationship(
        "Address", foreign_keys=[shipping_address_id]
    )
    billing_address: Mapped[Optional["Address"]] = relationship(
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
