from typing import Optional

from pydantic import BaseModel, EmailStr


class PaymentIntentCreate(BaseModel):
    order_id: int
    # A SavedPaymentMethod.id (not a Stripe id) — pass to pre-attach that
    # card to the PaymentIntent so the frontend can skip re-collecting card
    # details and go straight to confirming. Guest checkout has no saved
    # methods, so GuestPaymentIntentCreate below doesn't carry this.
    saved_payment_method_id: Optional[int] = None


class GuestPaymentIntentCreate(BaseModel):
    order_number: str
    email: EmailStr


class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: float
    currency: str


class PaymentWebhookEvent(BaseModel):
    type: str
    data: dict
