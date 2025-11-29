from sqlalchemy import Integer, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.db.database import Base


class Wishlist(Base):
    """Wishlist entity representing user's favorite/saved products."""

    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )

    # Unique constraint to prevent duplicate entries
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_wishlist"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="wishlist_items")
    product: Mapped["Product"] = relationship(
        "Product", back_populates="wishlist_items"
    )
