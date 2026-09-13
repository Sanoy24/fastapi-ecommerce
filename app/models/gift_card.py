import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class GiftCard(Base):
    """An admin-issued code redeemable once into a customer's store-credit
    balance (see User.store_credit_balance / StoreCreditTransaction).

    Deliberately all-or-nothing: redeeming a code moves its full value into
    the customer's fungible store-credit balance in one step rather than
    the gift card itself carrying a spendable remaining balance — partial
    spending is then just ordinary store-credit spending, tracked in
    StoreCreditTransaction like any other, so this table only ever needs
    to answer "has this code been redeemed, by whom, and when".
    """

    __tablename__ = "gift_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_redeemed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    redeemed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    redeemed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    # Admin-facing context for why this was issued (e.g. "goodwill refund
    # for order #123") — never shown to the customer who redeems it.
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.current_timestamp())

    @property
    def is_redeemable(self) -> bool:
        if self.is_redeemed:
            return False
        if self.expires_at and datetime.datetime.now() > self.expires_at:
            return False
        return True
