from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Request Schemas
class AddToWishlistRequest(BaseModel):
    """Request to add a product to wishlist"""

    product_id: int = Field(..., description="ID of the product to add to wishlist")


# Response Schemas
class WishlistItemResponse(BaseModel):
    """Wishlist item with product details"""

    id: int
    product_id: int
    product_name: str
    product_slug: str
    product_price: float
    product_image_url: Optional[str]
    product_stock_quantity: int
    product_is_active: bool
    added_at: datetime

    class Config:
        from_attributes = True


class WishlistResponse(BaseModel):
    """List of wishlist items"""

    items: List[WishlistItemResponse]
    total_count: int


class WishlistStatsResponse(BaseModel):
    """Wishlist statistics"""

    count: int = Field(..., description="Number of items in wishlist")


class WishlistActionResponse(BaseModel):
    """Response for wishlist actions"""

    message: str
    product_id: Optional[int] = None
