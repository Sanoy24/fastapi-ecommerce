from sqlalchemy import Column, Integer, ForeignKey, DateTime, Numeric, String
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.time import utcnow


class StoreCreditTransaction(Base):
    """One entry in a user's store-credit ledger — mirrors
    LoyaltyTransaction, but for a currency amount (User.store_credit_balance)
    instead of a points count. Credited by redeeming a GiftCard, spent at
    checkout, and reversed on cancellation/refund.
    """

    __tablename__ = "store_credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    # Set only for a "redeem_gift_card" row — which code actually funded it.
    gift_card_id = Column(Integer, ForeignKey("gift_cards.id", ondelete="SET NULL"), nullable=True)
    # Positive for "redeem_gift_card" and a spend-reversal (credit
    # restored), negative for "spend" — the sign is what actually changes
    # the balance; transaction_type is only for display/auditing.
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_type = Column(String(20), nullable=False)  # "redeem_gift_card", "spend", "reversal"
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")
    order = relationship("Order")
    gift_card = relationship("GiftCard")
