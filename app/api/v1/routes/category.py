from fastapi import APIRouter, Depends
from app.schema.category_schema import CreateCategory, UpdateCategory, CategoryPublic
from app.schema.user_schema import UserPublic
from app.dependencies import (
    get_category_service_dep,
    require_admin,
)
from app.services.category_service import CategoryService
from typing import Annotated

router = APIRouter(tags=["Category"])


category_dependency = Annotated[CategoryService, Depends(get_category_service_dep)]
admin_dependency = Annotated[UserPublic, Depends(require_admin)]


@router.post(
    "",
    response_model=CategoryPublic,
    status_code=201,
)
async def create_category(
    create_dto: CreateCategory,
    category_service: category_dependency,
    current_admin: admin_dependency,
):
    # If needed, use current_admin (e.g., log "Created by {current_admin.id}")
    category = category_service.create_category(create_dto)
    return category


@router.get("/{id}", response_model=CategoryPublic, status_code=200)
async def get_category_by_id(
    id: int,
    category_service: category_dependency,
    current_admin: admin_dependency,
) -> CategoryPublic:
    category = category_service.get_category_by_id(id)
    return category


# @router.get("/")
# async def get_category_by_slug():
#     pass


# @router.put()
# async def update_category():
#     pass


# @router.delete()
# async def delete_category():
#     pass
