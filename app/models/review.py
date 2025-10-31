from sqlalchemy import (
    Column,
    Integer,
    Text,
    ForeignKey,
    Integer,
    DateTime,
    Boolean,
    func,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    rating = Column(Integer)  # Add CHECK constraint via DB or validator in app
    comment = Column(Text)
    created_at = Column(DateTime, default=func.current_timestamp())
    is_approved = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="reviews")
    product = relationship("Product", back_populates="reviews")
