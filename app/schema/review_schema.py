from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ReviewBase(BaseModel):
    rating: int
    comment: Optional[str] = None


class ReviewCreate(ReviewBase):
    product_id: int


class ReviewUpdate(ReviewBase):
    # Widening rating to Optional for partial updates is intentional (standard
    # Update-DTO pattern); mypy's dataclass-style override check doesn't know
    # Pydantic allows this.
    rating: Optional[int] = None  # type: ignore[assignment]
    comment: Optional[str] = None


class ReviewResponse(ReviewBase):
    id: int
    user_id: int
    product_id: int
    created_at: datetime
    is_approved: bool

    model_config = ConfigDict(from_attributes=True)
