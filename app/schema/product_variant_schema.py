from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime

class ProductVariantCreate(BaseModel):
    sku: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    price: float = Field(..., gt=0)
    stock_quantity: int = Field(default=0, ge=0)
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool = True

class ProductVariantUpdate(BaseModel):
    sku: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=255)
    price: Optional[float] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ProductVariantResponse(BaseModel):
    id: int
    product_id: int
    sku: str
    name: str
    price: float
    stock_quantity: int
    attributes: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
