from sqlalchemy import String, Numeric, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.db.database import Base

class TaxRate(Base):
    """Tax rates applicable to orders."""

    __tablename__ = "tax_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)  # e.g., 0.1500 for 15%
    applies_to: Mapped[str] = mapped_column(
        SQLEnum("all", "category", "region", name="tax_applies_to"),
        default="all"
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
