from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SubscriptionInterval = Literal["weekly", "biweekly", "monthly"]


class SubscriptionCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = Field(1, ge=1)
    interval: SubscriptionInterval
    saved_payment_method_id: int
    shipping_address_id: int
    billing_address_id: int


class SubscriptionResponse(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    interval: str
    status: str
    next_billing_date: datetime
    failure_count: int
    last_payment_error: Optional[str] = None
    created_at: datetime
    cancelled_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
