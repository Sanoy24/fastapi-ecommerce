from sqlalchemy import ForeignKey, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from datetime import datetime
from app.db.database import Base


class Cart(Base):
    """Shopping cart entity associated with a user or a session."""

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    coupon_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
    # Set when an abandoned-cart recovery email is sent (see
    # app/workers/arq_worker.py detect_abandoned_carts_task). Without this,
    # the twice-daily cron would re-email the same still-abandoned cart on
    # every run forever — a cart becomes eligible again only once
    # last_activity_at has moved past this timestamp, i.e. the customer
    # touched their cart again since the last reminder.
    abandoned_email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="carts")
    coupon: Mapped[Optional["Coupon"]] = relationship("Coupon", back_populates="carts")
    cart_items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
