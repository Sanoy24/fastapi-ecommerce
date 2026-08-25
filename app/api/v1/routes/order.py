from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from app.schema.user_schema import UserPublic
from app.services.order_service import OrderService
from app.dependencies import get_current_user, get_order_service_dep, get_db, get_arq_pool
from app.schema.order_schema import OrderCreateRequest, OrderResponse
from app.utils.idempotency import check_idempotency, cache_idempotent_response
from fastapi import APIRouter, Depends, HTTPException, status, Request
from arq.connections import ArqRedis
from typing import Annotated
from app.core.limiter import limiter

router = APIRouter(tags=["Orders"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]
order_dependency = Annotated[OrderService, Depends(get_order_service_dep)]


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place a new order",
    response_model_exclude_none=True,
)
@limiter.limit("5/minute")
async def create_order(
    request: Request,
    order_create_request: OrderCreateRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    order_service: order_dependency,
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
    idempotency_key: str | None = Depends(check_idempotency),
):
    """
    Place a new order from the items currently in the cart.
    Requires valid shipping and billing address IDs.
    """
    order = await order_service.place_order(
        user_id=current_user.id,
        shipping_id=order_create_request.shipping_address_id,
        billing_id=order_create_request.billing_address_id,
        shipping_method_id=order_create_request.shipping_method_id,
    )

    if arq_pool:
        await arq_pool.enqueue_job(
            "send_order_confirmation_email_task",
            current_user.email,
            order.order_number,
            order.total_amount
        )

    if idempotency_key:
        from app.schema.order_schema import OrderResponse
        order_response = OrderResponse.model_validate(order)
        await cache_idempotent_response(idempotency_key, order_response.model_dump(mode="json"))

    return order


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

class RefundRequest(BaseModel):
    amount: float
    reason: str

@router.post("/{order_id}/refund")
def request_refund(
    order_id: int,
    request: RefundRequest,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Request a refund for an order.
    """
    from app.services.payment_service import PaymentService
    payment_service = PaymentService(db)
    return payment_service.refund_payment(
        order_id=order_id,
        user_id=current_user.id,
        amount=request.amount,
        reason=request.reason,
        is_admin=False
    )

class ReturnItem(BaseModel):
    order_item_id: int
    quantity: int
    reason: str

class ReturnCreateRequest(BaseModel):
    reason: str
    items: List[ReturnItem]

@router.post("/{order_id}/return")
def request_return(
    order_id: int,
    request: ReturnCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Request a return for a delivered order.
    """
    from app.crud.order import OrderCrud
    from app.models.return_request import ReturnRequest
    from app.core.exceptions import OrderException

    order_crud = OrderCrud(db)
    try:
        order = order_crud.get_order_by_id(current_user.id, order_id)
    except OrderException as e:
        raise HTTPException(status_code=404, detail=str(e))

    if order.status != "delivered":
        raise HTTPException(status_code=400, detail="Only delivered orders can be returned")

    # Basic validation that the items belong to the order
    order_item_ids = {item.id for item in order.order_items}
    for item in request.items:
        if item.order_item_id not in order_item_ids:
            raise HTTPException(status_code=400, detail=f"Item {item.order_item_id} not part of this order")

    return_req = ReturnRequest(
        order_id=order.id,
        user_id=current_user.id,
        reason=request.reason,
        items=[item.model_dump() for item in request.items]
    )
    db.add(return_req)

    # Update order status
    order_crud.update_order_status(order.id, "return_requested")

    db.commit()
    db.refresh(return_req)
    return return_req

