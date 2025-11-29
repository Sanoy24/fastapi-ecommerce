from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.database import Base
from sqlalchemy import (
    String,
    Numeric,
    ForeignKey,
    Text,
    func,
    select,
)
from sqlalchemy.ext.hybrid import hybrid_property
from typing import List, Optional
import datetime


class Product(Base):
    """Product entity representing items in the catalog."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(default=0)
    sku: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=func.current_timestamp()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=func.current_timestamp(), onupdate=func.now()
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    cart_items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="product", cascade="all, delete-orphan"
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="product", cascade="all, delete-orphan"
    )
    reviews: Mapped[List["Review"]] = relationship(
        "Review", back_populates="product", cascade="all, delete-orphan"
    )
    wishlist_items: Mapped[List["Wishlist"]] = relationship(
        "Wishlist", back_populates="product", cascade="all, delete-orphan"
    )

    @hybrid_property
    def average_rating(self) -> Optional[float]:
        """Calculate average rating from reviews (instance level)."""
        if not self.reviews:
            return None
        total = sum(review.rating for review in self.reviews)
        return round(total / len(self.reviews), 2)

    @average_rating.expression
    def average_rating(cls):
        """Calculate average rating for SQL queries (class level)."""
        from app.models.review import Review

        return (
            select(func.avg(Review.rating))
            .where(Review.product_id == cls.id)
            .correlate_except(Review)
            .scalar_subquery()
        )

    @hybrid_property
    def review_count(self) -> int:
        """Get total number of reviews (instance level)."""
        return len(self.reviews) if self.reviews else 0

    @review_count.expression
    def review_count(cls):
        """Get review count for SQL queries (class level)."""
        from app.models.review import Review

        return (
            select(func.count(Review.id))
            .where(Review.product_id == cls.id)
            .correlate_except(Review)
            .scalar_subquery()
        )

    @hybrid_property
    def in_stock(self) -> bool:
        """Check if product is in stock (instance level)."""
        return self.stock_quantity > 0

    @in_stock.expression
    def in_stock(cls):
        """Check stock availability for SQL queries (class level)."""
        return cls.stock_quantity > 0
