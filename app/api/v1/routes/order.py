from sqlalchemy.orm import Session
from typing import List
from app.schema.user_schema import UserPublic
from app.services.order_service import OrderService
from app.dependencies import get_current_user, get_order_service_dep, get_db, get_arq_pool
from app.schema.order_schema import (
    GuestOrderClaimLinkRequest,
    GuestOrderClaimRequest,
    GuestOrderCreateRequest,
    GuestOrderLookupRequest,
    OrderCreateRequest,
    OrderResponse,
)
from app.schema.return_schema import ReturnCreateRequest, ReturnResponse
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
    arq_pool: Annotated[ArqRedis | None, Depends(get_arq_pool)],
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


# --- Guest checkout ---
# Registered before GET/POST /{order_id}... below: Starlette matches routes
# in registration order, and /{order_id} would otherwise capture "guest" as
# its path parameter and 422 on the int conversion before this ever runs.

@router.post(
    "/guest",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Guest checkout",
    response_model_exclude_none=True,
)
@limiter.limit("5/minute")
async def create_guest_order(
    request: Request,
    guest_order_request: GuestOrderCreateRequest,
    order_service: order_dependency,
    arq_pool: Annotated[ArqRedis | None, Depends(get_arq_pool)],
    idempotency_key: str | None = Depends(check_idempotency),
):
    """
    Place an order from the current anonymous cart — no account required.
    Requires a session_id cookie, which the cart endpoints already set the
    moment a guest adds their first item.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cart found for this session. Add an item to your cart first.",
        )

    order = await order_service.place_guest_order(
        session_id=session_id,
        guest_email=guest_order_request.email,
        shipping_address=guest_order_request.shipping_address,
        billing_address=guest_order_request.billing_address,
        shipping_method_id=guest_order_request.shipping_method_id,
    )

    if arq_pool:
        await arq_pool.enqueue_job(
            "send_order_confirmation_email_task",
            guest_order_request.email,
            order.order_number,
            order.total_amount,
        )

    if idempotency_key:
        order_response = OrderResponse.model_validate(order)
        await cache_idempotent_response(idempotency_key, order_response.model_dump(mode="json"))

    return order


@router.post("/guest/lookup", response_model=OrderResponse, summary="Look up a guest order")
@limiter.limit("10/minute")
def lookup_guest_order(
    request: Request,
    lookup: GuestOrderLookupRequest,
    order_service: order_dependency,
):
    """Track a guest order by order number + the email it was placed with.
    Rate limited — this pair is the entire authorization, so it's the one
    thing worth slowing down guessing at."""
    return order_service.lookup_guest_order(lookup.order_number, lookup.email)


@router.post(
    "/guest/request-claim-link",
    summary="Email a link to save a guest order to an account",
)
@limiter.limit("5/minute")
async def request_guest_order_claim_link(
    request: Request,
    body: GuestOrderClaimLinkRequest,
    order_service: order_dependency,
    arq_pool: Annotated[ArqRedis | None, Depends(get_arq_pool)],
):
    """
    Always responds the same way regardless of whether order_number/email
    matched anything — same anti-enumeration shape as /users/forgot-password.
    """
    await order_service.request_guest_order_claim_link(body.order_number, body.email, arq_pool)
    return {
        "message": "If that order exists and hasn't already been claimed, "
        "we've emailed a link to save it to an account."
    }


@router.post(
    "/guest/claim",
    response_model=OrderResponse,
    summary="Attach a guest order to your account",
)
async def claim_guest_order(
    body: GuestOrderClaimRequest,
    current_user: user_dependency,
    order_service: order_dependency,
):
    """Consume a claim link's token (see /guest/request-claim-link) and
    attach that guest order to the signed-in account."""
    return await order_service.claim_guest_order(body.claim_token, current_user.id)


@router.get("", response_model=list[OrderResponse])
def list_orders(
    current_user: user_dependency,
    order_service: order_dependency,
):
    return order_service.list_orders(current_user.id)


@router.get("/returns", response_model=List[ReturnResponse], summary="List your return requests")
def list_my_returns(
    current_user: user_dependency,
    db: Session = Depends(get_db),
):
    """
    Registered before GET /{order_id} below for the same reason the guest
    routes are: /{order_id} would otherwise capture "returns" as its path
    parameter and 422 on the int conversion before this ever runs.
    """
    from app.models.return_request import ReturnRequest
    from sqlalchemy import select

    stmt = (
        select(ReturnRequest)
        .where(ReturnRequest.user_id == current_user.id)
        .order_by(ReturnRequest.created_at.desc())
    )
    return db.scalars(stmt).all()


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

# Refunds are admin-only — see POST /admin/orders/{order_id}/refund. Customers
# request a refund by filing a return via POST /{order_id}/return below, which
# an admin then approves and refunds through the admin endpoint.

@router.post("/{order_id}/return", response_model=ReturnResponse)
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

    # Validate that the items belong to the order and the quantity claimed
    # doesn't exceed what was actually ordered — checked again defensively
    # at approval time (see admin.py resolve_return), but catching it here
    # means the customer finds out immediately instead of after an admin
    # rejects a pending request days later.
    order_items_by_id = {item.id: item for item in order.order_items}
    for item in request.items:
        order_item = order_items_by_id.get(item.order_item_id)
        if not order_item:
            raise HTTPException(status_code=400, detail=f"Item {item.order_item_id} not part of this order")
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Return quantity for item {item.order_item_id} must be positive")
        if item.quantity > order_item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot return {item.quantity} of item {item.order_item_id} — only {order_item.quantity} were ordered",
            )

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

