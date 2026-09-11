from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.time import utcnow

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    # Set when the transaction is against a specific variant's own stock_quantity
    # rather than the base product's.
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    transaction_type = Column(String(50), nullable=False)  # "reservation", "deduction", "adjustment", "return"
    quantity_change = Column(Integer, nullable=False)  # positive = stock added, negative = stock removed
    quantity_before = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    note = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    product = relationship("Product")
    variant = relationship("ProductVariant")
    order = relationship("Order")
    creator = relationship("User")
