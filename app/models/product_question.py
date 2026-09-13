from datetime import datetime
from typing import List

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ProductQuestion(Base):
    """A customer's question about a product, publicly askable and
    answerable by any signed-in user — deliberately not gated on having
    purchased the product, unlike Review, since people ask questions to
    help decide whether to buy in the first place."""

    __tablename__ = "product_questions"
    __table_args__ = (
        Index("ix_product_questions_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=func.current_timestamp()
    )

    product: Mapped["Product"] = relationship("Product")
    user: Mapped["User"] = relationship("User")
    answers: Mapped[List["ProductAnswer"]] = relationship(
        "ProductAnswer", back_populates="question", cascade="all, delete-orphan",
        order_by="ProductAnswer.created_at",
    )
