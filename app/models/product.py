from sqlalchemy.orm import relationship
from app.db.database import Base
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    func,
)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    stock_quantity = Column(Integer, default=0)
    sku = Column(String(100), unique=True)
    image_url = Column(String(500))
    category_id = Column(Integer, ForeignKey("categories.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relationships
    category = relationship("Category", back_populates="products")
    cart_items = relationship(
        "CartItem", back_populates="product", cascade="all, delete-orphan"
    )
    order_items = relationship(
        "OrderItem", back_populates="product", cascade="all, delete-orphan"
    )
    reviews = relationship(
        "Review", back_populates="product", cascade="all, delete-orphan"
    )
