from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Integer,
    Numeric,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    payment_method = Column(
        SQLEnum("credit_card", "paypal", "bank_transfer", name="payment_method"),
        nullable=False,
    )
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(
        SQLEnum("pending", "completed", "failed", name="payment_status"),
        default="pending",
    )
    transaction_id = Column(String(100))
    paid_at = Column(DateTime, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="payments")
