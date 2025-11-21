from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ReviewBase(BaseModel):
    rating: int
    comment: Optional[str] = None


class ReviewCreate(ReviewBase):
    product_id: int


class ReviewUpdate(ReviewBase):
    rating: Optional[int] = None
    comment: Optional[str] = None


class ReviewResponse(ReviewBase):
    id: int
    user_id: int
    product_id: int
    created_at: datetime
    is_approved: bool

    model_config = ConfigDict(from_attributes=True)
