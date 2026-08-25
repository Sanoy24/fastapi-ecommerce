from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from app.schema.common_schema import PaginatedResponse, CursorPaginatedResponse
from app.schema.product_schema import ProductCreate, ProductUpdate, ProductResponse
from app.schema.search_schema import (
    AvailabilityFilter,
    SortByField,
    SortOrder,
    ProductAutocompleteResponse,
)
from app.services.product_service import ProductService
from app.dependencies import get_product_service_dep, require_admin
from app.schema.user_schema import UserPublic
from app.utils.upload import save_product_image
from typing import Annotated, List, Union
from app.core.logger import logger
from fastapi_cache.decorator import cache

router = APIRouter(tags=["Product"])
product_dependency = Annotated[ProductService, Depends(get_product_service_dep)]
admin_dependency = Annotated[UserPublic, Depends(require_admin)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProductResponse)
async def create_product(
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


@router.get("", response_model=Union[PaginatedResponse[ProductResponse], CursorPaginatedResponse[ProductResponse]])
@cache(expire=60)
async def get_all_products(
    product_service: product_dependency,
    cursor: Annotated[int | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
    search: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    category_id: Annotated[int | None, Query(ge=1)] = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    availability: AvailabilityFilter = AvailabilityFilter.ALL,
    sort_by: SortByField = SortByField.ID,
    sort_order: SortOrder = SortOrder.ASC,
) -> Union[PaginatedResponse[ProductResponse], CursorPaginatedResponse[ProductResponse]]:
    """
    Get all products with advanced filtering and sorting. If `cursor` is provided, uses cursor pagination (faster).
    """
    if cursor is not None:
        return product_service.get_all_products_cursor(cursor, limit)
        
    return product_service.get_all_products(
        page,
        per_page,
        search,
        category_id,
        min_price,
        max_price,
        min_rating,
        availability.value,
        sort_by.value,
        sort_order.value,
    )


@router.get("/autocomplete", response_model=ProductAutocompleteResponse)
async def get_product_autocomplete(
    product_service: product_dependency,
    q: Annotated[str, Query(min_length=2, max_length=100, description="Search query")],
) -> ProductAutocompleteResponse:
    """
    Get product name suggestions for autocomplete.

    **Requirements:**
    - Query must be at least 2 characters
    - Returns maximum 10 suggestions
    - Results are cached for 1 hour

    **Matching:**
    - Prioritizes products that start with the query
    - Falls back to products containing the query
    - Case-insensitive matching
    """
    suggestions = await product_service.get_autocomplete_suggestions(q)
    return ProductAutocompleteResponse(suggestions=suggestions)


@router.get("/category/{slug}", response_model=List[ProductResponse])
async def get_products_by_category_slug(
    slug: Annotated[str, Path(title="The category slug")],
    product_service: product_dependency,
) -> List[ProductResponse]:
    return product_service.get_products_by_category_slug(slug)


@router.get("/id/{id}", response_model=ProductResponse)
@cache(expire=3600)
async def get_product_by_id(
    id: int, product_service: product_dependency, current_admin: admin_dependency
) -> ProductResponse:
    return await product_service.get_product_by_id(id)


@router.get("/{slug}", response_model=ProductResponse)
async def get_product_by_slug(
    slug: Annotated[str, Path(title="The slug of the item to get")],
    product_service: product_dependency,
) -> ProductResponse:
    return product_service.get_product_by_slug(slug)


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


@router.post(
    "/{id}/image",
    response_model=ProductResponse,
    summary="Upload product image",
    description=(
        "Upload an image for a product. "
        "Accepted formats: JPEG, PNG, WebP, GIF (max 5 MB). "
        "Admin only."
    ),
)
async def upload_product_image(
    id: int,
    product_service: product_dependency,
    current_admin: admin_dependency,
    file: UploadFile = File(..., description="Product image file"),
) -> ProductResponse:
    """Upload and attach an image to an existing product."""
    image_url = await save_product_image(file)
    return product_service.update_product(id, update_dto=ProductUpdate(image_url=image_url))


from app.schema.product_image_schema import ProductImageResponse
from fastapi import Form

@router.get("/{id}/images", response_model=List[ProductImageResponse])
async def get_product_gallery_images(
    id: int,
    product_service: product_dependency,
):
    return product_service.get_gallery_images(id)


@router.post("/{id}/images", response_model=ProductImageResponse, summary="Upload gallery image")
async def upload_gallery_image(
    id: int,
    product_service: product_dependency,
    current_admin: admin_dependency,
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    alt_text: str = Form(None),
):
    image_url = await save_product_image(file)
    return product_service.add_gallery_image(id, image_url, is_primary, alt_text)


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gallery_image(
    image_id: int,
    product_service: product_dependency,
    current_admin: admin_dependency,
):
    product_service.delete_gallery_image(image_id)


from app.schema.product_variant_schema import ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse

@router.post("/{id}/variants", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED)
async def create_product_variant(
    id: int,
    variant_dto: ProductVariantCreate,
    product_service: product_dependency,
    current_admin: admin_dependency,
):
    return product_service.add_product_variant(id, variant_dto)

@router.get("/{id}/variants", response_model=List[ProductVariantResponse])
async def get_product_variants(
    id: int,
    product_service: product_dependency,
):
    return product_service.get_product_variants(id)

@router.put("/variants/{variant_id}", response_model=ProductVariantResponse)
async def update_product_variant(
    variant_id: int,
    variant_dto: ProductVariantUpdate,
    product_service: product_dependency,
    current_admin: admin_dependency,
):
    return product_service.update_product_variant(variant_id, variant_dto)

@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_variant(
    variant_id: int,
    product_service: product_dependency,
    current_admin: admin_dependency,
):
    product_service.delete_product_variant(variant_id)

from app.schema.product_schema import ProductRelationCreate, ProductRelationResponse

@router.post("/{id}/relations", response_model=ProductRelationResponse, status_code=status.HTTP_201_CREATED)
async def create_product_relation(
    id: int,
    relation_dto: ProductRelationCreate,
    product_service: product_dependency,
    current_admin: admin_dependency,
):
    return product_service.add_product_relation(id, relation_dto)

@router.get("/{id}/relations", response_model=List[ProductRelationResponse])
async def get_product_relations(
    id: int,
    product_service: product_dependency,
):
    return product_service.get_product_relations(id)

@router.delete("/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_relation(
    relation_id: int,
    product_service: product_dependency,
    current_admin: admin_dependency,
):
    product_service.delete_product_relation(relation_id)

