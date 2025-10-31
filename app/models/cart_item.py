from sqlalchemy import Column, ForeignKey, Integer, DateTime,Integer, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class CartItem(Base):
    __tablename__ = "cartitems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(
        Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity = Column(Integer, default=1)
    added_at = Column(DateTime, default=func.current_timestamp())

    # Relationships
    cart = relationship("Cart", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")
