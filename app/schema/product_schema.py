# class Product(Base):
#     __tablename__ = "products"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     name = Column(String(255), nullable=False)
#     slug = Column(String(255), unique=True, nullable=False)
#     description = Column(Text)
#     price = Column(Numeric(10, 2), nullable=False)
#     stock_quantity = Column(Integer, default=0)
#     sku = Column(String(100), unique=True)
#     image_url = Column(String(500))
#     category_id = Column(Integer, ForeignKey("categories.id"))
#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=func.current_timestamp())

#     # Relationships
#     category = relationship("Category", back_populates="products")
#     cart_items = relationship(
#         "CartItem", back_populates="product", cascade="all, delete-orphan"
#     )
#     order_items = relationship(
#         "OrderItem", back_populates="product", cascade="all, delete-orphan"
#     )
#     reviews = relationship(
#         "Review", back_populates="product", cascade="all, delete-orphan"
#     )


from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional
from datetime import datetime
import re


class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    # slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    stock_quantity: Optional[int] = Field(0, ge=0)
    # sku: Optional[str] = Field(None, max_length=100)
    image_url: Optional[HttpUrl] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = True


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    sku: Optional[str] = Field(None, max_length=100)
    image_url: Optional[HttpUrl] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("slug")
    def validate_slug(cls, v):
        if v and not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return v


class ProductResponse(ProductBase):
    """Schema for returning product data."""

    id: int
    created_at: datetime
    slug: str
    sku: str

    model_config = {"from_attributes": True}
