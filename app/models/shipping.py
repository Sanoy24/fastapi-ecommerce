from sqlalchemy import String, Numeric, Boolean, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.db.database import Base

class ShippingZone(Base):
    __tablename__ = "shipping_zones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    countries: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of country codes

    rates: Mapped[list["ShippingRate"]] = relationship("ShippingRate", back_populates="zone", cascade="all, delete-orphan")

class ShippingMethod(Base):
    __tablename__ = "shipping_methods"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    carrier: Mapped[str] = mapped_column(String(100), nullable=False)
    estimated_days_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_days_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    base_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    per_kg_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rates: Mapped[list["ShippingRate"]] = relationship("ShippingRate", back_populates="method", cascade="all, delete-orphan")

class ShippingRate(Base):
    __tablename__ = "shipping_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("shipping_zones.id", ondelete="CASCADE"), nullable=False)
    method_id: Mapped[int] = mapped_column(ForeignKey("shipping_methods.id", ondelete="CASCADE"), nullable=False)
    base_rate_override: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    per_kg_rate_override: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    zone: Mapped["ShippingZone"] = relationship("ShippingZone", back_populates="rates")
    method: Mapped["ShippingMethod"] = relationship("ShippingMethod", back_populates="rates")
