from fastapi import APIRouter, Depends, status
from app.schema.product_schema import ProductCreate, ProductResponse
from app.services.product_service import ProductService
from app.dependencies import get_product_service_dep, require_admin
from app.schema.user_schema import UserPublic
from typing import Annotated
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
