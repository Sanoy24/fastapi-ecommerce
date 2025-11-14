from fastapi import APIRouter, Depends, Path, status
from app.schema.product_schema import ProductCreate, ProductUpdate, ProductResponse
from app.services.product_service import ProductService
from app.dependencies import get_product_service_dep, require_admin
from app.schema.user_schema import UserPublic
from typing import Annotated, List
from app.core.logger import logger

router = APIRouter(tags=["Product"])
product_dependency = Annotated[ProductService, Depends(get_product_service_dep)]
admin_dependency = Annotated[UserPublic, Depends(require_admin)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProductResponse)
async def create_prodcut(
    create_dto: ProductCreate,
    product_service: product_dependency,
    current_admin: admin_dependency,
) -> ProductResponse:
    product = product_service.create_product(create_dto)
    # for traceabilty purpose
    logger.info(
        f"current user creating the product: {current_admin.id} product: {product.id}"
    )
    return product


@router.get("", response_model=List[ProductResponse])
async def get_all_products(
    product_service: product_dependency,
) -> List[ProductResponse]:
    return product_service.get_all_products()


@router.get("/{slug}", response_model=ProductResponse)
async def get_product_by_slug(
    slug: Annotated[str, Path(title="The slug of the item to get")],
    product_service: product_dependency,
) -> ProductResponse:
    return product_service.get_product_by_slug(slug)


@router.get("/category/{slug}", response_model=List[ProductResponse])
async def get_products_by_category_slug(
    slug: Annotated[str, Path(title="The category slug")],
    product_service: product_dependency,
) -> List[ProductResponse]:
    return product_service.get_products_by_category_slug(slug)


@router.get("/{id}", response_model=ProductResponse)
async def get_product_by_id(
    id: int, product_service: product_dependency, current_admin: admin_dependency
) -> ProductResponse:
    return product_service.get_product_by_id(id)


@router.put("/{id}", response_model=ProductResponse)
async def update_product(
    id: int,
    update_dto: ProductUpdate,
    product_service: product_dependency,
    current_admin: admin_dependency,
) -> ProductResponse:
    return product_service.update_product(id, update_dto)


@router.delete("/{id}")
async def delete_product(
    id: int, product_service: product_dependency, current_admin: admin_dependency
):
    product_service.delete_product(id)
    return {"detail": "product deleted successfully"}
