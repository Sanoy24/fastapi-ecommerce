from pydantic import BaseModel, Field
from typing import Optional


# ---- Base ----
class AddressBase(BaseModel):
    type: str = Field(max_length=20)
    street: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)
    is_default: Optional[bool] = False


# ---- Create ----
class AddressCreate(AddressBase):
    pass


# ---- Update ----
class AddressUpdate(BaseModel):
    type: Optional[str] = Field(default=None, max_length=20)
    street: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)
    is_default: Optional[bool] = None

    model_config = {"from_attributes": True}


# ---- Public / Response ----
class AddressPublic(AddressBase):
    id: int
    user_id: int

    model_config = {"from_attributes": True}
