from pydantic import BaseModel, EmailStr


class PaymentIntentCreate(BaseModel):
    order_id: int


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
