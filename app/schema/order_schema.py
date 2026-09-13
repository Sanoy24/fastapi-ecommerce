from pydantic import BaseModel, EmailStr, Field
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


class ShipmentResponse(BaseModel):
    """The Shipment row's own status/estimated_delivery/delivered_at — a
    finer-grained view than the tracking_number/shipping_carrier/shipped_at
    columns duplicated onto Order itself below, and the only place
    estimated_delivery and a delivered/in_transit/failed status live."""
    id: int
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    status: str
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    estimated_delivery: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OrderEventResponse(BaseModel):
    """One entry in an order's status timeline (placed, paid, shipped, ...)."""
    from_status: Optional[str] = None
    to_status: str
    note: Optional[str] = None
    created_at: datetime

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
    # subtotal/tax_amount/shipping_amount/total_amount above are always in
    # the store's base currency — currency_code/exchange_rate_at_purchase
    # record what this specific order was actually charged in (see
    # PaymentService._create_payment_intent_for_order).
    currency_code: str
    exchange_rate_at_purchase: float = 1.0
    points_redeemed: int = 0
    points_earned: int = 0
    store_credit_applied: float = 0.0
    notes: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    order_items: List[OrderItemResponse]
    shipments: List[ShipmentResponse] = []
    events: List[OrderEventResponse] = []

    model_config = {"from_attributes": True}


class OrderCreateRequest(BaseModel):
    shipping_address_id: int
    billing_address_id: int
    shipping_method_id: Optional[int] = None


# ---- Guest checkout ----
# A guest has no saved Address row, so checkout takes the address content
# directly instead of an address_id. Field names deliberately match
# app.models.address.Address / OrderCrud._address_snapshot so the same
# snapshot logic works unchanged for both a real Address row and this.
class GuestAddressInput(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)


class GuestOrderCreateRequest(BaseModel):
    email: EmailStr
    shipping_address: GuestAddressInput
    billing_address: GuestAddressInput
    shipping_method_id: Optional[int] = None


class GuestOrderLookupRequest(BaseModel):
    """Order number + email is the guest's proof of ownership — both are
    only known to whoever placed or received the order confirmation."""
    order_number: str
    email: EmailStr


class GuestOrderClaimLinkRequest(BaseModel):
    order_number: str
    email: EmailStr


class GuestOrderClaimRequest(BaseModel):
    claim_token: str
