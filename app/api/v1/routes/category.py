from fastapi import APIRouter, Depends
from app.schema.category_schema import CreateCategory, UpdateCategory, CategoryPublic
from app.schema.user_schema import UserPublic
from app.dependencies import (
    get_category_service_dep,
    require_admin,
)
from app.services.category_service import CategoryService
from typing import Annotated, List

router = APIRouter(tags=["Category"])


category_dependency = Annotated[CategoryService, Depends(get_category_service_dep)]
admin_dependency = Annotated[UserPublic, Depends(require_admin)]


@router.post(
    "",
    response_model=CategoryPublic,
    status_code=201,
    summary="Create category",
    description="Create a new category (admin only).",
)
async def create_category(
    create_dto: CreateCategory,
    category_service: category_dependency,
    current_admin: admin_dependency,
):
    """Create a category and return its public representation."""
    # If needed, use current_admin (e.g., log "Created by {current_admin.id}")
    category = category_service.create_category(create_dto)
    return category


@router.get(
    "",
    response_model=List[CategoryPublic],
    summary="List categories",
    description="Returns all categories.",
)
async def get_all_categories(
    category_service: category_dependency,
):
    """List all categories."""
    return category_service.get_all_categories()


@router.get(
    "/{id}",
    response_model=CategoryPublic,
    status_code=200,
    summary="Get category by id",
    description="Retrieve a category by id (admin only).",
)
async def get_category_by_id(
    id: int,
    category_service: category_dependency,
    current_admin: admin_dependency,
) -> CategoryPublic:
    """Get a category by id (admin only)."""
    category = category_service.get_category_by_id(id)
    return category


@router.get(
    "/{slug}",
    summary="Get category by slug",
    description="Retrieve a category by slug (admin only).",
)
async def get_category_by_slug(
    slug: str, category_service: category_dependency, current_admin: admin_dependency
):
    """Get a category by slug (admin only)."""
    category = category_service.get_category_by_slug(slug)
    return category


@router.put(
    "/{id}",
    summary="Update category",
    description="Partially update a category (admin only).",
)
async def update_category(
    id: int,
    update_dto: UpdateCategory,
    category_service: category_dependency,
    current_admin: admin_dependency,
):
    """Update a category by id (admin only)."""
    updated_category = category_service.update_category(id, update_dto)
    return updated_category


@router.delete(
    "/{id}",
    summary="Delete category",
    description="Delete a category by id (admin only).",
)
async def delete_category(
    id: int,
    category_service: category_dependency,
    current_admin: admin_dependency,
):
    """Delete a category by id (admin only)."""
    category_service.delete_category(id)
    return {"detail": "category deleted successfully"}
