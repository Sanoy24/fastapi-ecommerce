from sqlalchemy import Integer, ForeignKey, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from datetime import datetime
from app.db.database import Base


class Cart(Base):
    """Shopping cart entity associated with a user or a session."""

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="carts")
    cart_items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
