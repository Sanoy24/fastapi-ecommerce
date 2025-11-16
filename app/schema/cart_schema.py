from pydantic import BaseModel, Field
from typing import List


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product_name: str  # ✅ FIXED: should be string
    unit_price: float
    subtotal: float

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    id: int
    items: List[CartItemResponse]
    total_items: int
    subtotal: float  # ✅ FIXED: name must match service output

    model_config = {"from_attributes": True}
