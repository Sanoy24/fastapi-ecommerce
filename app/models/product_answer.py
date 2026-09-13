from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ProductAnswer(Base):
    """One answer to a ProductQuestion. Any signed-in user can answer,
    not just an admin/seller — crowd-sourced, matching how the question
    side is open too."""

    __tablename__ = "product_answers"
    __table_args__ = (
        Index("ix_product_answers_question_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("product_questions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=func.current_timestamp()
    )

    question: Mapped["ProductQuestion"] = relationship("ProductQuestion", back_populates="answers")
    user: Mapped["User"] = relationship("User")
