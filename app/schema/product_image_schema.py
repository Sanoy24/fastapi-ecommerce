from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import Optional
from datetime import datetime

class ProductImageResponse(BaseModel):
    id: int
    product_id: int
    url: str
    alt_text: Optional[str]
    is_primary: bool
    display_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
