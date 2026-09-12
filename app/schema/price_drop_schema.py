from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PriceDropSubscribeRequest(BaseModel):
    product_id: int
    target_price: Optional[float] = Field(
        None, gt=0, description="Notify once the price falls to this amount or below. Omit to be notified on any price drop."
    )


class PriceDropSubscriptionResponse(BaseModel):
    id: int
    product_id: int
    subscribed_price: float
    target_price: Optional[float] = None
    created_at: datetime
    notified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
