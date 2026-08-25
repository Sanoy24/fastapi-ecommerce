from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    tracking_number = Column(String(100), nullable=True)
    carrier = Column(String(100), nullable=True)
    status = Column(String(50), default="pending")  # "pending", "shipped", "in_transit", "delivered", "failed"
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    estimated_delivery = Column(DateTime, nullable=True)
    shipment_items = Column(JSON, nullable=True)  # [{order_item_id, quantity}]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order", back_populates="shipments")
