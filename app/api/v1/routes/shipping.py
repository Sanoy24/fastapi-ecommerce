from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.dependencies import get_db, require_admin
from app.models.shipping import ShippingMethod, ShippingZone, ShippingRate
from app.schema.shipping_schema import (
    ShippingMethodCreate, ShippingMethodResponse,
    ShippingZoneCreate, ShippingZoneResponse,
    ShippingRateCreate, ShippingRateResponse
)
from app.models.user import User
from app.services.admin_service import AdminService

router = APIRouter(prefix="/shipping", tags=["shipping"])
admin_router = APIRouter(prefix="/admin/shipping", tags=["admin-shipping"])

@router.get("/methods", response_model=List[ShippingMethodResponse])
def get_shipping_methods(db: Session = Depends(get_db)):
    stmt = select(ShippingMethod).where(ShippingMethod.is_active == True)
    return db.scalars(stmt).all()

@admin_router.post("/methods", response_model=ShippingMethodResponse, status_code=status.HTTP_201_CREATED)
def create_shipping_method(
    data: ShippingMethodCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    method = ShippingMethod(**data.model_dump())
    db.add(method)
    db.commit()
    db.refresh(method)
    AdminService(db).log_action(admin.id, "CREATE_SHIPPING_METHOD", "shipping_method", method.id, new_value=data.model_dump())
    return method

@admin_router.post("/zones", response_model=ShippingZoneResponse, status_code=status.HTTP_201_CREATED)
def create_shipping_zone(
    data: ShippingZoneCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    zone = ShippingZone(**data.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    AdminService(db).log_action(admin.id, "CREATE_SHIPPING_ZONE", "shipping_zone", zone.id, new_value=data.model_dump())
    return zone

@admin_router.post("/rates", response_model=ShippingRateResponse, status_code=status.HTTP_201_CREATED)
def create_shipping_rate(
    data: ShippingRateCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    rate = ShippingRate(**data.model_dump())
    db.add(rate)
    db.commit()
    db.refresh(rate)
    AdminService(db).log_action(admin.id, "CREATE_SHIPPING_RATE", "shipping_rate", rate.id, new_value=data.model_dump())
    return rate
