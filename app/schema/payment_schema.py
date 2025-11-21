from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PaymentIntentCreate(BaseModel):
    order_id: int


class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: float
    currency: str


class PaymentWebhookEvent(BaseModel):
    type: str
    data: dict
