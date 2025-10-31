from sqlalchemy import Column, ForeignKey, DateTime, String, func, Integer
from sqlalchemy.orm import relationship
from app.db.database import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    session_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(
        DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    user = relationship("User", back_populates="carts")
    cart_items = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
