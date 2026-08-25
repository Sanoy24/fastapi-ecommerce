from sqlalchemy import Integer, Text, ForeignKey, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from datetime import datetime
from app.db.database import Base
from sqlalchemy import Index


class Review(Base):
    """Product review entity with rating and optional comment."""

    __tablename__ = "reviews"
    __table_args__ = (
        Index("ix_reviews_product_id_approved", "product_id", "is_approved"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    helpful_votes: Mapped[int] = mapped_column(Integer, default=0)
    unhelpful_votes: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="reviews")
    product: Mapped["Product"] = relationship("Product", back_populates="reviews")
