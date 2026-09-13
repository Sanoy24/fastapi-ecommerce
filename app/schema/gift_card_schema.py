from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class GiftCardIssueRequest(BaseModel):
    value: float = Field(..., gt=0)
    note: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[datetime] = None


class GiftCardResponse(BaseModel):
    id: int
    code: str
    value: float
    is_redeemed: bool
    redeemed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RedeemGiftCardRequest(BaseModel):
    code: str


class ApplyStoreCreditRequest(BaseModel):
    amount: float = Field(..., gt=0)


class StoreCreditBalanceResponse(BaseModel):
    balance: float


class StoreCreditTransactionResponse(BaseModel):
    id: int
    amount: float
    transaction_type: str
    note: Optional[str] = None
    order_id: Optional[int] = None
    gift_card_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StoreCreditTransactionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    transactions: List[StoreCreditTransactionResponse]
