from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PriceDropSubscription(Base):
    """A customer's request to be emailed when a product's price drops.

    One row per (user, product) ever — re-subscribing after already being
    notified re-arms this same row (clears notified_at, refreshes
    subscribed_price/target_price) rather than inserting a new one, matching
    BackInStockSubscription's approach. See PriceDropService.subscribe.
    """

    __tablename__ = "price_drop_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_price_drop_subscription"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Product.effective_price at the moment of subscribing — the baseline a
    # "notify on any drop" subscription (target_price is None) compares
    # against, since there's no explicit target to check instead.
    subscribed_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # None means "notify on any decrease from subscribed_price". Set means
    # "only notify once effective_price falls to this amount or below" —
    # letting a customer wait for a specific price rather than any drop.
    target_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User")
    product: Mapped["Product"] = relationship("Product")
