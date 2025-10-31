from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    Numeric,
    String,
    Integer,
    DateTime,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum
from app.db.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    shipping_address_id = Column(
        Integer, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    billing_address_id = Column(
        Integer, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    order_number = Column(String(50), unique=True, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(
        SQLEnum(
            "pending", "paid", "shipped", "delivered", "cancelled", name="order_status"
        ),
        default="pending",
    )
    order_date = Column(DateTime, default=func.current_timestamp())
    shipped_at = Column(DateTime, nullable=True)
    tx_ref = Column(String(255), unique=True)
    payment_status = Column(
        SQLEnum("pending", "success", "failed", name="payment_status"),
        default="pending",
    )

    # Relationships
    user = relationship("User", back_populates="orders")
    shipping_address = relationship("Address", foreign_keys=[shipping_address_id])
    billing_address = relationship("Address", foreign_keys=[billing_address_id])
    order_items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    payments = relationship(
        "Payment", back_populates="order", cascade="all, delete-orphan"
    )
