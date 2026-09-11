from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, JSON
from app.db.database import Base
from app.utils.time import utcnow
from sqlalchemy.ext.hybrid import hybrid_property
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
    created_at = Column(DateTime, default=utcnow)

    product = relationship("Product", back_populates="variants")
    reservations = relationship(
        "InventoryReservation", back_populates="variant", cascade="all, delete-orphan"
    )

    # Relationships for future use
    # cart_items = relationship("CartItem", back_populates="variant")
    # order_items = relationship("OrderItem", back_populates="variant")

    @hybrid_property
    def available_stock(self) -> int:
        """Stock quantity minus this variant's own active reservations.

        A variant's stock_quantity is a separate pool from its parent
        product's — see Product.available_stock, which excludes
        variant-scoped reservations for the same reason.
        """
        if not self.reservations:
            return int(self.stock_quantity)
        now = utcnow()
        active_reservations_qty = sum(
            res.quantity for res in self.reservations if res.expires_at > now
        )
        return int(self.stock_quantity) - active_reservations_qty
