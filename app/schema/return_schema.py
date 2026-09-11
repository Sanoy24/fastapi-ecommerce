from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel


class ReturnItemRequest(BaseModel):
    order_item_id: int
    quantity: int
    reason: str


class ReturnCreateRequest(BaseModel):
    reason: str
    items: List[ReturnItemRequest]


class ReturnItemInfo(BaseModel):
    order_item_id: int
    quantity: int
    reason: str


class ReturnResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    reason: str
    status: str
    items: List[ReturnItemInfo]
    resolution_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    # Response-only: set when an approval's automatic refund attempt
    # failed, so the return is approved and restocked but still needs a
    # manual refund via POST /admin/orders/{order_id}/refund. Never
    # persisted on the ReturnRequest row itself.
    refund_error: Optional[str] = None

    model_config = {"from_attributes": True}


class ReturnResolutionRequest(BaseModel):
    status: str  # approved, rejected
    resolution_note: str
