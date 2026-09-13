from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RedeemPointsRequest(BaseModel):
    points: int = Field(..., gt=0)


class LoyaltyBalanceResponse(BaseModel):
    points_balance: int


class LoyaltyTransactionResponse(BaseModel):
    id: int
    points: int
    transaction_type: str
    note: Optional[str] = None
    order_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoyaltyTransactionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    transactions: List[LoyaltyTransactionResponse]
