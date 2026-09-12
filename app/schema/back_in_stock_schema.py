from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BackInStockSubscribeRequest(BaseModel):
    product_id: int
    variant_id: Optional[int] = None


class BackInStockSubscriptionResponse(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    created_at: datetime
    notified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
