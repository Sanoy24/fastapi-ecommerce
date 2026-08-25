from pydantic import BaseModel, Field
from typing import List, Optional

class ShippingZoneBase(BaseModel):
    name: str = Field(..., max_length=100)
    countries: Optional[List[str]] = None

class ShippingZoneCreate(ShippingZoneBase):
    pass

class ShippingZoneResponse(ShippingZoneBase):
    id: int
    model_config = {"from_attributes": True}

class ShippingMethodBase(BaseModel):
    name: str = Field(..., max_length=100)
    carrier: str = Field(..., max_length=100)
    estimated_days_min: Optional[int] = None
    estimated_days_max: Optional[int] = None
    base_rate: float = Field(0.0, ge=0)
    per_kg_rate: float = Field(0.0, ge=0)
    is_active: bool = True

class ShippingMethodCreate(ShippingMethodBase):
    pass

class ShippingMethodResponse(ShippingMethodBase):
    id: int
    model_config = {"from_attributes": True}

class ShippingRateBase(BaseModel):
    zone_id: int
    method_id: int
    base_rate_override: Optional[float] = None
    per_kg_rate_override: Optional[float] = None

class ShippingRateCreate(ShippingRateBase):
    pass

class ShippingRateResponse(ShippingRateBase):
    id: int
    model_config = {"from_attributes": True}
