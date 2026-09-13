from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Subscription(Base):
    """A customer's recurring order for one product (optionally one
    variant) at a fixed quantity and interval, charged automatically
    against a saved payment method.

    Deliberately one product per subscription rather than a cart-shaped
    multi-item subscription: a customer wanting several recurring products
    on independent schedules just creates several rows, and the renewal
    billing job (see app/workers/arq_worker.py
    process_due_subscriptions_task) never has to reconcile partial-item
    failures within a single cycle.

    shipping_address_id/billing_address_id are snapshotted at subscribe
    time, the same way Order.shipping_address_id is chosen once at
    checkout — a later change to the customer's default address doesn't
    retroactively move where a running subscription ships.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_id_status", "user_id", "status"),
        Index("ix_subscriptions_next_billing_date", "next_billing_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    interval: Mapped[str] = mapped_column(
        SQLEnum("weekly", "biweekly", "monthly", name="subscription_interval"),
        nullable=False,
    )
    # RESTRICT, not SET NULL: a subscription can't function without a
    # payment method to charge, so deleting one still in use is refused at
    # the application level — see
    # SavedPaymentMethodService.delete_method's active-subscription check —
    # rather than silently leaving a subscription that can never renew.
    saved_payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("saved_payment_methods.id", ondelete="RESTRICT"), nullable=False
    )
    shipping_address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    billing_address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SQLEnum("active", "paused", "past_due", "cancelled", name="subscription_status"),
        default="active",
        nullable=False,
    )
    next_billing_date: Mapped[datetime] = mapped_column(nullable=False)
    # Consecutive failed renewal attempts. Reset to 0 on any successful
    # charge; once it exceeds the retry schedule the subscription is
    # cancelled automatically — see
    # app/utils/subscription_billing.py RETRY_SCHEDULE_DAYS.
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_payment_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.current_timestamp())
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship("User")
    product: Mapped["Product"] = relationship("Product")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant")
    saved_payment_method: Mapped["SavedPaymentMethod"] = relationship("SavedPaymentMethod")
    shipping_address: Mapped["Address"] = relationship("Address", foreign_keys=[shipping_address_id])
    billing_address: Mapped["Address"] = relationship("Address", foreign_keys=[billing_address_id])
