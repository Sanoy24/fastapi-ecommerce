from pydantic import BaseModel, Field
from typing import List


class CartItemCreate(BaseModel):
    product_id: int
    variant_id: int | None = None
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    variant_id: int | None = None
    quantity: int
    product_name: str  # ✅ FIXED: should be string
    unit_price: float
    subtotal: float

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    id: int
    items: List[CartItemResponse]
    total_items: int
    subtotal: float
    coupon_code: str | None = None
    discount_amount: float = 0.0
    estimated_tax: float = 0.0
    total_amount: float
    points_redeemed: int = 0
    points_discount_amount: float = 0.0
    loyalty_points_balance: int = 0
    # subtotal/total_amount above are always in the store's base currency.
    # currency_code/display_* reflect whichever currency was selected via
    # PUT /cart/currency — equal to the base figures when none was.
    currency_code: str
    exchange_rate_to_base: float = 1.0
    display_subtotal: float
    display_total_amount: float

    model_config = {"from_attributes": True}
