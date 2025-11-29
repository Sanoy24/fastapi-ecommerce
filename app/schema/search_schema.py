from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AvailabilityFilter(str, Enum):
    """Filter products by stock availability."""

    ALL = "all"
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"


class SortByField(str, Enum):
    """Available fields for sorting products."""

    ID = "id"
    NAME = "name"
    PRICE = "price"
    RATING = "rating"
    POPULARITY = "popularity"
    CREATED_AT = "created_at"


class SortOrder(str, Enum):
    """Sort order direction."""

    ASC = "asc"
    DESC = "desc"


class ProductSearchParams(BaseModel):
    """
    Comprehensive search and filter parameters for product queries.

    This schema encapsulates all possible search, filter, and sort options
    for product listings, making it easier to validate and document API parameters.
    """

    # Pagination
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=10, ge=1, le=100, description="Items per page")

    # Search
    search: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search term for product name and description",
    )

    # Filters
    category_id: Optional[int] = Field(
        default=None, ge=1, description="Filter by category ID"
    )
    min_price: Optional[float] = Field(
        default=None, ge=0, description="Minimum price filter"
    )
    max_price: Optional[float] = Field(
        default=None, ge=0, description="Maximum price filter"
    )
    min_rating: Optional[float] = Field(
        default=None, ge=0, le=5, description="Minimum average rating (0-5)"
    )
    availability: AvailabilityFilter = Field(
        default=AvailabilityFilter.ALL, description="Filter by stock availability"
    )

    # Sorting
    sort_by: SortByField = Field(default=SortByField.ID, description="Field to sort by")
    sort_order: SortOrder = Field(
        default=SortOrder.ASC, description="Sort direction (ascending or descending)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "page": 1,
                    "per_page": 20,
                    "search": "phone",
                    "category_id": 5,
                    "min_price": 100,
                    "max_price": 1000,
                    "min_rating": 4.0,
                    "availability": "in_stock",
                    "sort_by": "price",
                    "sort_order": "asc",
                }
            ]
        }
    }


class ProductAutocompleteResponse(BaseModel):
    """Response schema for product autocomplete suggestions."""

    suggestions: list[str] = Field(
        description="List of product name suggestions (max 10)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "suggestions": [
                        "iPhone 16 Pro",
                        "iPhone 16",
                        "iPhone 15 Pro Max",
                        "iPhone 14",
                    ]
                }
            ]
        }
    }
