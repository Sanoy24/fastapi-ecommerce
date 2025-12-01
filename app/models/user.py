from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    DateTime,
    Integer,
    func,
    Enum as SQLEnum,
)
from app.db.database import Base


class User(Base):
    """User entity for authentication and profile data."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(
        SQLEnum("customer", "admin", name="user_roles"), default="customer"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), onupdate=func.now()
    )

    # Relationships
    addresses: Mapped[List["Address"]] = relationship(
        "Address", back_populates="user", cascade="all, delete-orphan"
    )
    carts: Mapped[List["Cart"]] = relationship("Cart", back_populates="user")
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="user", cascade="all, delete-orphan"
    )
    reviews: Mapped[List["Review"]] = relationship(
        "Review", back_populates="user", cascade="all, delete-orphan"
    )
    wishlist_items: Mapped[List["Wishlist"]] = relationship(
        "Wishlist", back_populates="user", cascade="all, delete-orphan"
    )
