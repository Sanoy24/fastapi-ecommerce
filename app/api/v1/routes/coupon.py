from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from app.dependencies import require_admin, get_coupon_service_dep
from app.schema.coupon_schema import CouponCreate, CouponUpdate, CouponPublic
from app.services.coupon_service import CouponService

router = APIRouter(tags=["Coupons"])

coupon_service_dep = Annotated[CouponService, Depends(get_coupon_service_dep)]
admin_dep = Annotated[dict, Depends(require_admin)]


@router.post("", response_model=CouponPublic)
def create_coupon(
    coupon_data: CouponCreate,
    coupon_service: coupon_service_dep,
    admin_user: admin_dep,
):
    """Create a new coupon code (Admin only)."""
    return coupon_service.create_coupon(coupon_data)


@router.get("", response_model=List[CouponPublic])
def list_coupons(
    coupon_service: coupon_service_dep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """List all coupons (Public endpoint for viewing available promos, though usually restricted)."""
    return coupon_service.list_coupons(skip, limit)


@router.get("/{coupon_id}", response_model=CouponPublic)
def get_coupon(
    coupon_id: int,
    coupon_service: coupon_service_dep,
    admin_user: admin_dep,
):
    """Get coupon details (Admin only)."""
    return coupon_service.get_coupon(coupon_id)


@router.put("/{coupon_id}", response_model=CouponPublic)
def update_coupon(
    coupon_id: int,
    coupon_data: CouponUpdate,
    coupon_service: coupon_service_dep,
    admin_user: admin_dep,
):
    """Update a coupon (Admin only)."""
    return coupon_service.update_coupon(coupon_id, coupon_data)


@router.delete("/{coupon_id}", status_code=204)
def delete_coupon(
    coupon_id: int,
    coupon_service: coupon_service_dep,
    admin_user: admin_dep,
):
    """Delete a coupon (Admin only)."""
    coupon_service.delete_coupon(coupon_id)
