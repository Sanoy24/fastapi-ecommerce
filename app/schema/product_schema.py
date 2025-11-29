from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional
from datetime import datetime
import re


class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    stock_quantity: Optional[int] = Field(0, ge=0)
    image_url: Optional[HttpUrl] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = True


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "I Phone 16",
                    "description": "A new I phone with the highest tech",
                    "price": "1000",
                    "stock_quantity": 10,
                    "image_url": "https://image.com",
                }
            ]
        }
    }


class ProductUpdate(BaseModel):
    """Schema for updating a product."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    sku: Optional[str] = Field(None, max_length=100)
    image_url: Optional[HttpUrl] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    """Schema for returning product data."""

    id: int
    created_at: datetime
    slug: str
    sku: str
    average_rating: Optional[float] = Field(
        None, ge=0, le=5, description="Average rating from reviews (0-5)"
    )
    review_count: int = Field(default=0, ge=0, description="Total number of reviews")
    in_stock: bool = Field(description="Whether product is currently in stock")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "name": "I Phone 16",
                    "description": "A new I phone with the highest tech",
                    "price": 1000,
                    "stock_quantity": 10,
                    "image_url": "https://image.com/",
                    "category_id": None,
                    "is_active": True,
                    "id": 2,
                    "created_at": "2025-11-14T08:21:58",
                    "slug": "i-phone-16-1",
                    "sku": "PRD-IPHON-E10F",
                    "average_rating": 4.5,
                    "review_count": 24,
                    "in_stock": True,
                }
            ]
        },
    }
