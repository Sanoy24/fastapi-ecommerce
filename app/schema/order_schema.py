from pydantic import BaseModel
from typing import List
from datetime import datetime


class OrderItemResponse(BaseModel):
    product_id: int
    quantity: int
    unit_price: float

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    order_number: str
    total_amount: float
    status: str
    order_date: datetime
    order_items: List[OrderItemResponse]

    model_config = {"from_attributes": True}


class OrderCreateRequest(BaseModel):
    shipping_address_id: int
    billing_address_id: int
