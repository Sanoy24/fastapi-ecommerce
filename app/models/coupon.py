import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, Integer, Numeric, Boolean, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Coupon(Base):
    """Coupon entity for discounts and promotions."""

    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    discount_type: Mapped[str] = mapped_column(SQLEnum("percentage", "fixed", name="discount_types"), nullable=False)
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Optional limits
    min_order_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    valid_from: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    valid_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime.datetime] = mapped_column(default=func.current_timestamp())
    updated_at: Mapped[datetime.datetime] = mapped_column(default=func.current_timestamp(), onupdate=func.now())

    # Relationships
    carts: Mapped[List["Cart"]] = relationship("Cart", back_populates="coupon")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="coupon")

    @property
    def is_valid(self) -> bool:
        """Check if the coupon is currently valid based on active status, dates, and usage limits."""
        if not self.is_active:
            return False

        now = datetime.datetime.now()

        if self.valid_from and now < self.valid_from:
            return False

        if self.valid_until and now > self.valid_until:
            return False

        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False

        return True
