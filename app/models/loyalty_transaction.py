from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.time import utcnow


class LoyaltyTransaction(Base):
    """One entry in a user's loyalty-points ledger — earned, redeemed, or
    reversed. User.loyalty_points_balance is the fast-read running total;
    this table is the audit trail behind it, the same event-log-plus-
    denormalized-column pattern as InventoryTransaction/stock_quantity.
    """

    __tablename__ = "loyalty_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    # Positive for "earn" and a redeem-reversal (points restored), negative
    # for "redeem" and an earn-reversal (points clawed back) — the sign is
    # what actually changes the balance; transaction_type is only for
    # display/auditing.
    points = Column(Integer, nullable=False)
    transaction_type = Column(String(20), nullable=False)  # "earn", "redeem", "reversal"
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")
    order = relationship("Order")
