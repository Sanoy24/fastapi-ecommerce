from sqlalchemy import Integer, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.db.database import Base


class OrderItem(Base):
    """Order line item representing a product and quantity in an order."""

    __tablename__ = "orderitems"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="order_items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant")
