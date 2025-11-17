from fastapi import APIRouter, Depends
from app.schema.user_schema import UserPublic
from app.services.order_service import OrderService
from app.dependencies import get_current_user, get_order_service_dep
from app.schema.order_schema import OrderCreateRequest, OrderResponse
from typing import Annotated

router = APIRouter(tags=["Orders"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]
order_dependency = Annotated[OrderService, Depends(get_order_service_dep)]


@router.post("", response_model=OrderResponse)
def place_order(
    payload: OrderCreateRequest,
    current_user: user_dependency,
    order_service: order_dependency,
):
    return order_service.place_order(
        user_id=current_user.id,
        shipping_id=payload.shipping_address_id,
        billing_id=payload.billing_address_id,
    )


@router.get("", response_model=list[OrderResponse])
def list_orders(
    current_user: user_dependency,
    order_service: order_dependency,
):
    return order_service.list_orders(current_user.id)


@router.get("/{order_id}", response_model=OrderResponse)
def get_single_order(
    current_user: user_dependency, order_service: order_dependency, order_id: int
):
    return order_service.get_one_order(current_user.id, order_id)
