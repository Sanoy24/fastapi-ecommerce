import datetime
from pydantic import BaseModel, Field
from typing import Optional


class CouponBase(BaseModel):
    code: str = Field(..., max_length=50, description="The unique promotional code.")
    discount_type: str = Field(..., description="'percentage' or 'fixed'.")
    discount_value: float = Field(..., gt=0, description="The discount amount or percentage.")
    min_order_value: Optional[float] = Field(None, description="Minimum order value to apply.")
    usage_limit: Optional[int] = Field(None, description="Max number of times this coupon can be used.")
    valid_from: Optional[datetime.datetime] = None
    valid_until: Optional[datetime.datetime] = None
    is_active: bool = True


class CouponCreate(CouponBase):
    pass


class CouponUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    discount_type: Optional[str] = None
    discount_value: Optional[float] = Field(None, gt=0)
    min_order_value: Optional[float] = None
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime.datetime] = None
    valid_until: Optional[datetime.datetime] = None
    is_active: Optional[bool] = None

    model_config = {"from_attributes": True}


class CouponPublic(CouponBase):
    id: int
    used_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
