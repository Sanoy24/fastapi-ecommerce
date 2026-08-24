from app.schema.user_schema import UserPublic
from app.services.order_service import OrderService
from app.dependencies import get_current_user, get_order_service_dep
from app.schema.order_schema import OrderCreateRequest, OrderResponse
from app.utils.idempotency import check_idempotency, cache_idempotent_response
from app.services.email_service import send_order_confirmation_email
from fastapi import APIRouter, Depends, BackgroundTasks
from typing import Annotated

router = APIRouter(tags=["Orders"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]
order_dependency = Annotated[OrderService, Depends(get_order_service_dep)]


@router.post("", response_model=OrderResponse)
async def place_order(
    payload: OrderCreateRequest,
    current_user: user_dependency,
    order_service: order_dependency,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Depends(check_idempotency),
):
    response_data = order_service.place_order(
        user_id=current_user.id,
        shipping_id=payload.shipping_address_id,
        billing_id=payload.billing_address_id,
    )
    
    background_tasks.add_task(
        send_order_confirmation_email,
        to_address=current_user.email,
        order_number=response_data.order_number,
        total_amount=response_data.total_amount
    )
    
    if idempotency_key:
        await cache_idempotent_response(idempotency_key, response_data.model_dump())
        
    return response_data


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


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel order",
    description=(
        "Cancel a pending order. Stock is restored for all items. "
        "Only orders in 'pending' status can be cancelled."
    ),
)
def cancel_order(
    order_id: int,
    current_user: user_dependency,
    order_service: order_dependency,
):
    """Cancel a pending order and restore product stock."""
    return order_service.cancel_order(user_id=current_user.id, order_id=order_id)

