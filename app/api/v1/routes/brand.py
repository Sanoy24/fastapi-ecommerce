from fastapi import APIRouter, Depends, status
from typing import Annotated, List
from app.schema.brand_schema import BrandCreate, BrandUpdate, BrandResponse
from app.schema.user_schema import UserPublic
from app.services.brand_service import BrandService
from app.dependencies import get_brand_service_dep, require_admin

router = APIRouter(tags=["Brands"])

brand_dependency = Annotated[BrandService, Depends(get_brand_service_dep)]
admin_dependency = Annotated[UserPublic, Depends(require_admin)]


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    create_dto: BrandCreate,
    brand_service: brand_dependency,
    current_admin: admin_dependency,
):
    return brand_service.create_brand(create_dto)


@router.get("", response_model=List[BrandResponse])
async def get_all_brands(brand_service: brand_dependency):
    return brand_service.get_all_brands()


@router.get("/{id}", response_model=BrandResponse)
async def get_brand_by_id(id: int, brand_service: brand_dependency):
    return brand_service.get_brand_by_id(id)


@router.get("/slug/{slug}", response_model=BrandResponse)
async def get_brand_by_slug(slug: str, brand_service: brand_dependency):
    return brand_service.get_brand_by_slug(slug)


@router.put("/{id}", response_model=BrandResponse)
async def update_brand(
    id: int,
    update_dto: BrandUpdate,
    brand_service: brand_dependency,
    current_admin: admin_dependency,
):
    return brand_service.update_brand(id, update_dto)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    id: int,
    brand_service: brand_dependency,
    current_admin: admin_dependency,
):
    brand_service.delete_brand(id)
