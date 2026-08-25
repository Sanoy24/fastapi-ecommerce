from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from datetime import datetime

from app.db.database import Base


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        SQLEnum("buy_x_get_y", "free_shipping", "percentage_on_category", name="promotion_type"),
        nullable=False
    )
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rewards: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
