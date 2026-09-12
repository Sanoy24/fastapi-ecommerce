from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class BackInStockSubscription(Base):
    """A customer's request to be emailed when a product (or a specific
    variant) becomes available again.

    One row per (user, product, variant) ever — re-subscribing after
    already being notified re-arms this same row (clears notified_at)
    rather than inserting a new one, so the unique constraint below stays
    meaningful instead of needing to account for a history of past,
    already-fulfilled subscriptions. See BackInStockService.subscribe.
    """

    __tablename__ = "back_in_stock_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "product_id", "variant_id", name="uq_back_in_stock_subscription"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # None means "the base product, no specific variant" — a product with
    # variants has a separate stock pool per variant (see
    # ProductVariant.available_stock), so a subscription has to be scoped
    # the same way to mean anything.
    variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User")
    product: Mapped["Product"] = relationship("Product")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant")
