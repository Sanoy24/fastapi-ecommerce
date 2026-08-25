from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float

    model_config = {"from_attributes": True}


class AddressSummary(BaseModel):
    id: int
    street: str
    city: str
    country: str

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    order_number: str
    total_amount: float
    status: str
    order_date: datetime
    shipped_at: Optional[datetime] = None
    tracking_number: Optional[str] = None
    shipping_carrier: Optional[str] = None
    tx_ref: str
    payment_status: str
    
    discount_amount: float
    subtotal: float
    tax_amount: float
    shipping_amount: float
    notes: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    order_items: List[OrderItemResponse]

    model_config = {"from_attributes": True}


class OrderCreateRequest(BaseModel):
    shipping_address_id: int
    billing_address_id: int
