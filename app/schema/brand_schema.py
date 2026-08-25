from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class BrandCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True

class BrandUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class BrandResponse(BaseModel):
    id: int
    name: str
    slug: str
    logo_url: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
