from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, JSON
from datetime import datetime
from app.db.database import Base
from sqlalchemy.orm import relationship

class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stock_quantity = Column(Integer, default=0)
    attributes = Column(JSON, nullable=True) # e.g. {"color": "Red", "size": "XL"}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="variants")
    
    # Relationships for future use
    # cart_items = relationship("CartItem", back_populates="variant")
    # order_items = relationship("OrderItem", back_populates="variant")
