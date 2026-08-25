from pydantic import BaseModel, Field
from typing import Optional

class TaxRateBase(BaseModel):
    name: str = Field(..., max_length=100)
    rate: float = Field(..., ge=0)
    applies_to: str = Field(..., description="all, category, region")
    category_id: Optional[int] = None
    region: Optional[str] = Field(None, max_length=100)
    is_active: bool = True

class TaxRateCreate(TaxRateBase):
    pass

class TaxRateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    rate: Optional[float] = Field(None, ge=0)
    applies_to: Optional[str] = Field(None, description="all, category, region")
    category_id: Optional[int] = None
    region: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

class TaxRateResponse(TaxRateBase):
    id: int

    model_config = {"from_attributes": True}
