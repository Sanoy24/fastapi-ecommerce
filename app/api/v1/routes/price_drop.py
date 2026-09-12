from typing import Annotated, List

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_price_drop_service_dep
from app.schema.price_drop_schema import (
    PriceDropSubscribeRequest,
    PriceDropSubscriptionResponse,
)
from app.schema.user_schema import UserPublic
from app.services.price_drop_service import PriceDropService

router = APIRouter(tags=["Price Drop Alerts"])

service_dep = Annotated[PriceDropService, Depends(get_price_drop_service_dep)]
user_dep = Annotated[UserPublic, Depends(get_current_user)]


@router.post(
    "",
    response_model=PriceDropSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Get notified when a product's price drops",
)
def subscribe(
    request: PriceDropSubscribeRequest,
    service: service_dep,
    current_user: user_dep,
):
    """Subscribe to an email when this product's price drops — either any
    decrease from the current price, or once it falls to a given
    target_price."""
    return service.subscribe(
        user_id=current_user.id,
        product_id=request.product_id,
        target_price=request.target_price,
    )


@router.get(
    "",
    response_model=List[PriceDropSubscriptionResponse],
    summary="List your price-drop alert subscriptions",
)
def list_my_subscriptions(
    service: service_dep,
    current_user: user_dep,
):
    return service.list_my_subscriptions(user_id=current_user.id)


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a price-drop alert subscription",
)
def unsubscribe(
    subscription_id: int,
    service: service_dep,
    current_user: user_dep,
):
    service.unsubscribe(user_id=current_user.id, subscription_id=subscription_id)
