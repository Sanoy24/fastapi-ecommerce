from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    current_page: int = Field(..., description="Current page number (1-based)")
    per_page: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    total_items: int = Field(..., description="Total number of items across all pages")
    from_item: Optional[int] = Field(None, description="Starting item index (1-based)")
    to_item: Optional[int] = Field(None, description="Ending item index (1-based)")


class PaginationLinks(BaseModel):
    self: Optional[str] = Field(None, description="URL to the current page")
    first: Optional[str] = Field(None, description="URL to the first page")
    prev: Optional[str] = Field(
        None, description="URL to the previous page, or null if none"
    )
    next: Optional[str] = Field(
        None, description="URL to the next page, or null if none"
    )
    last: Optional[str] = Field(None, description="URL to the last page")


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T] = Field(..., description="List of items for the current page")
    meta: PaginationMeta = Field(..., description="Pagination metadata")
    links: Optional[PaginationLinks] = Field(
        None, description="HATEOAS links for navigation"
    )
