from typing import Annotated
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_payment_service_dep
from app.schema.user_schema import UserPublic
from app.services.payment_service import PaymentService
from app.schema.payment_schema import PaymentIntentCreate, PaymentIntentResponse
from app.api.v1.routes.user import get_current_user

router = APIRouter(tags=["payments"])

user_dependency = Annotated[UserPublic, Depends(get_db)]
payment_service_dep = Annotated[PaymentService, Depends(get_payment_service_dep)]


@router.post("/create-intent", response_model=PaymentIntentResponse)
def create_payment_intent(
    payment_data: PaymentIntentCreate,
    payment_service: payment_service_dep,
    current_user=Depends(get_current_user),
):
    return payment_service.create_payment_intent(current_user.id, payment_data.order_id)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    payment_service: payment_service_dep,
    stripe_signature: str = Header(None),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    payload = await request.body()
    return payment_service.handle_webhook(payload, stripe_signature)
