from typing import Annotated, List

from fastapi import APIRouter, Depends, status

from app.dependencies import get_back_in_stock_service_dep, get_current_user
from app.schema.back_in_stock_schema import (
    BackInStockSubscribeRequest,
    BackInStockSubscriptionResponse,
)
from app.schema.user_schema import UserPublic
from app.services.back_in_stock_service import BackInStockService

router = APIRouter(tags=["Back In Stock"])

service_dep = Annotated[BackInStockService, Depends(get_back_in_stock_service_dep)]
user_dep = Annotated[UserPublic, Depends(get_current_user)]


@router.post(
    "",
    response_model=BackInStockSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Get notified when an out-of-stock item is available again",
)
def subscribe(
    request: BackInStockSubscribeRequest,
    service: service_dep,
    current_user: user_dep,
):
    """Subscribe to an email the moment this product (or variant) is
    restocked. Only allowed while the item is actually out of stock."""
    return service.subscribe(
        user_id=current_user.id,
        product_id=request.product_id,
        variant_id=request.variant_id,
    )


@router.get(
    "",
    response_model=List[BackInStockSubscriptionResponse],
    summary="List your back-in-stock subscriptions",
)
def list_my_subscriptions(
    service: service_dep,
    current_user: user_dep,
):
    return service.list_my_subscriptions(user_id=current_user.id)


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a back-in-stock subscription",
)
def unsubscribe(
    subscription_id: int,
    service: service_dep,
    current_user: user_dep,
):
    service.unsubscribe(user_id=current_user.id, subscription_id=subscription_id)
