from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    transaction_type = Column(String(50), nullable=False)  # "reservation", "deduction", "adjustment", "return"
    quantity_change = Column(Integer, nullable=False)  # positive = stock added, negative = stock removed
    quantity_before = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    note = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")
    order = relationship("Order")
    creator = relationship("User")
