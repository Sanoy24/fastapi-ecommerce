from typing import Annotated
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from app.dependencies import get_payment_service_dep
from app.schema.user_schema import UserPublic
from app.services.payment_service import PaymentService
from app.schema.payment_schema import GuestPaymentIntentCreate, PaymentIntentCreate, PaymentIntentResponse
from app.api.v1.routes.user import get_current_user
from app.utils.idempotency import check_idempotency, cache_idempotent_response
from app.core.limiter import limiter

router = APIRouter(tags=["payments"])

payment_service_dep = Annotated[PaymentService, Depends(get_payment_service_dep)]


@router.post("/create-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    payment_data: PaymentIntentCreate,
    payment_service: payment_service_dep,
    current_user: UserPublic = Depends(get_current_user),
    idempotency_key: str | None = Depends(check_idempotency),
):
    response_data = payment_service.create_payment_intent(
        current_user.id, payment_data.order_id, payment_data.saved_payment_method_id
    )

    if idempotency_key:
        await cache_idempotent_response(idempotency_key, response_data.model_dump())

    return response_data


@router.post("/guest/create-intent", response_model=PaymentIntentResponse, summary="Create a payment intent for a guest order")
@limiter.limit("10/minute")
async def create_guest_payment_intent(
    request: Request,
    payment_data: GuestPaymentIntentCreate,
    payment_service: payment_service_dep,
    idempotency_key: str | None = Depends(check_idempotency),
):
    """
    Order number + email stands in for authentication here — the same
    proof-of-ownership pair as the other guest order endpoints. Rate
    limited since, unlike a logged-in checkout, nothing else here would
    slow down someone guessing at that pair.
    """
    response_data = payment_service.create_guest_payment_intent(payment_data.order_number, payment_data.email)

    if idempotency_key:
        await cache_idempotent_response(idempotency_key, response_data.model_dump())

    return response_data


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    payment_service: payment_service_dep,
    stripe_signature: str = Header(None),
):
    """
    Handle Stripe webhook events (e.g. payment_intent.succeeded)
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    payload = await request.body()
    return payment_service.handle_webhook(payload, stripe_signature)
