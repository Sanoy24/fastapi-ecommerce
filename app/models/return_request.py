from sqlalchemy import Integer, String, ForeignKey, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.db.database import Base

class ReturnRequest(Base):
    __tablename__ = "return_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, approved, rejected
    items: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)  # [{order_item_id, quantity, reason}]
    resolution_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp(), onupdate=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order")
    user: Mapped["User"] = relationship("User")
