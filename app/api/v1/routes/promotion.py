from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_promotion_service_dep, require_admin
from app.schema.promotion_schema import PromotionCreate, PromotionResponse, PromotionUpdate
from app.services.promotion_service import PromotionService

router = APIRouter(tags=["Promotions"])

promotion_service_dep = Annotated[PromotionService, Depends(get_promotion_service_dep)]
admin_dep = Annotated[dict, Depends(require_admin)]


@router.post("", response_model=PromotionResponse)
def create_promotion(
    data: PromotionCreate,
    promotion_service: promotion_service_dep,
    admin_user: admin_dep,
):
    """Create a new promotion (Admin only).

    Previously the only way to create one was writing to the promotions
    table directly with SQL — checkout has correctly applied active
    promotions to the cart and to orders for a while, but nothing let an
    admin actually configure one through the API.
    """
    return promotion_service.create_promotion(data)


@router.get("", response_model=List[PromotionResponse])
def list_promotions(
    promotion_service: promotion_service_dep,
    admin_user: admin_dep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    active_only: Optional[bool] = Query(None, description="Only currently active promotions"),
):
    """List all promotions (Admin only)."""
    return promotion_service.list_promotions(skip, limit, active_only=bool(active_only))


@router.get("/{promotion_id}", response_model=PromotionResponse)
def get_promotion(
    promotion_id: int,
    promotion_service: promotion_service_dep,
    admin_user: admin_dep,
):
    """Get promotion details (Admin only)."""
    return promotion_service.get_promotion(promotion_id)


@router.put("/{promotion_id}", response_model=PromotionResponse)
def update_promotion(
    promotion_id: int,
    data: PromotionUpdate,
    promotion_service: promotion_service_dep,
    admin_user: admin_dep,
):
    """Update a promotion (Admin only)."""
    return promotion_service.update_promotion(promotion_id, data)


@router.delete("/{promotion_id}", status_code=204)
def delete_promotion(
    promotion_id: int,
    promotion_service: promotion_service_dep,
    admin_user: admin_dep,
):
    """Delete a promotion (Admin only)."""
    promotion_service.delete_promotion(promotion_id)
