from sqlalchemy import Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.db.database import Base
from sqlalchemy import Index

class InventoryReservation(Base):
    """Temporary stock reservation for an order in progress."""

    __tablename__ = "inventory_reservations"
    __table_args__ = (
        Index("ix_inventory_reservations_expires_product", "expires_at", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    # Set when the reservation is for a specific variant rather than the base
    # product — the variant has its own stock_quantity, a separate pool from
    # the parent product's, so it needs its own reservation tracking.
    variant_id: Mapped["int | None"] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="reservations")
    variant: Mapped["ProductVariant | None"] = relationship("ProductVariant", back_populates="reservations")
    user: Mapped["User"] = relationship("User")

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
