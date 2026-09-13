from datetime import datetime

from sqlalchemy import Boolean, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Currency(Base):
    """A currency customers can shop and check out in.

    Product prices are never stored per-currency — every price in this
    catalog stays denominated in settings.BASE_CURRENCY_CODE (see
    app/core/config.py), and this table only holds the rate used to
    convert *from* that base into each other currency for display and at
    checkout. That keeps every existing price/analytics/revenue
    calculation untouched: Order.total_amount and friends stay in base
    currency always (see Order.currency_code /
    exchange_rate_at_purchase for what a specific order was actually
    charged in), so summing revenue across orders never risks silently
    mixing currencies.
    """

    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)  # ISO 4217, e.g. "USD"
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # "US Dollar"
    symbol: Mapped[str] = mapped_column(String(5), nullable=False)  # "$"
    # Units of this currency equal to 1 unit of the base currency — the
    # base currency's own row always has exchange_rate_to_base = 1.
    # converted = base_amount * exchange_rate_to_base.
    exchange_rate_to_base: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
