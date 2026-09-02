from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import ProductException
from app.core.logger import logger
from app.core.redis import RedisClient
from app.crud.category import CategoryCrud
from app.crud.product import ProductCrud, allowed_sort_by, allowed_sort_order
from app.schema.product_schema import ProductCreate, ProductResponse, ProductUpdate
from app.schema.common_schema import PaginatedResponse, CursorPaginatedResponse
from app.schema.product_image_schema import ProductImageResponse
from app.schema.product_variant_schema import ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse


class ProductService:
    def __init__(self, db: Session, redis: RedisClient):
        self.db = db
        self.redis_client = redis
        self.crud = ProductCrud(db=db)

    def create_product(self, create_dto: ProductCreate) -> ProductResponse:
        """Create a product and return a validated response model."""
        try:
            result = self.crud.create_product(create_dto)
            return ProductResponse.model_validate(result)
        except ProductException as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=409, detail="Product already exists.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid product data"
            )
        except Exception as e:
            logger.info(f"exception: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="please try again",
            )

    def get_product_by_slug(self, slug: str) -> ProductResponse:
        """Retrieve a product by slug; 404 if not found."""
        product = self.crud.get_product_detail(slug)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )
        return ProductResponse.model_validate(product)

    async def get_product_by_id(self, id: int) -> ProductResponse:
        """Retrieve a product by id with caching."""
        cache_key = f"product:{id}"

        # Try cache first (store as JSON string for speed)
        cached_json = await self.redis_client.get_json(cache_key)
        if cached_json:
            logger.info(
                f"Cache hit for product: {id}",
            )
            return ProductResponse.model_validate_json(cached_json)

        logger.info("Cache miss for product:%s", id)

        # ← FIX: Must be await + async CRUD!
        product_model = self.crud.get_product_by_id(id)

        if not product_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        response_data = ProductResponse.model_validate(product_model)

        # Cache for 10 minutes (adjust as needed)
        await self.redis_client.set_json(
            cache_key, response_data.model_dump_json(), ex=600
        )

        return response_data

    def get_all_products(
        self,
        page: int,
        per_page: int,
        search: str | None = None,
        category_id: int | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        min_rating: float | None = None,
        availability: str | None = "all",
        sort_by: allowed_sort_by | None = "id",
        sort_order: allowed_sort_order = "asc",
    ) -> PaginatedResponse[ProductResponse]:
        """
        List all products with advanced filtering and sorting.

        Args:
            page: Page number
            per_page: Items per page
            search: Search term for name/description
            category_id: Filter by category
            min_price: Minimum price
            max_price: Maximum price
            min_rating: Minimum average rating (0-5)
            availability: Stock filter ('all', 'in_stock', 'out_of_stock')
            sort_by: Sort field
            sort_order: Sort direction ('asc' or 'desc')
        """
        try:
            products = self.crud.get_all_products(
                page,
                per_page,
                search,
                category_id,
                min_price,
                max_price,
                min_rating,
                availability,
                sort_by,
                sort_order,
            )
            return products
        except Exception as e:
            logger.info(f"exception: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="failed to fetch products",
            )

    def get_all_products_cursor(
        self,
        cursor: int | None = None,
        limit: int = 20
    ) -> CursorPaginatedResponse[ProductResponse]:
        try:
            products = self.crud.list_products_cursor(cursor, limit)
            products.data = [ProductResponse.model_validate(p) for p in products.data]
            return products
        except Exception as e:
            logger.info(f"exception: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="failed to fetch products by cursor",
            )

    def update_product(self, id: int, update_dto: ProductUpdate) -> ProductResponse:
        """Partially update a product; maps conflicts and not-found to HTTP codes."""
        try:
            updated = self.crud.update_product(id, update_dto)
            if not updated:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
                )
            return ProductResponse.model_validate(updated)
        except ProductException as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=409, detail="Duplicate product data")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid product update data",
            )
        except Exception as e:
            logger.info(f"exception: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="please try again",
            )

    def delete_product(self, id: int) -> None:
        """Delete a product by id; 404 if missing."""
        deleted = self.crud.delete_product(id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )
        return None

    def get_products_by_category_id(self, category_id: int) -> List[ProductResponse]:
        products = self.crud.get_products_by_category_id(category_id)
        return [ProductResponse.model_validate(p) for p in products]

    def get_products_by_category_slug(self, slug: str) -> List[ProductResponse]:
        category = CategoryCrud(self.db).get_category_by_slug(slug)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        products = self.crud.get_products_by_category_id(category.id)
        return [ProductResponse.model_validate(p) for p in products]

    async def get_autocomplete_suggestions(self, query: str) -> List[str]:
        """
        Get product name suggestions for autocomplete with Redis caching.

        Args:
            query: Search query (minimum 2 characters)

        Returns:
            List of product name suggestions (max 10)
        """
        if not query or len(query) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query must be at least 2 characters",
            )

        # Normalize query for cache key
        cache_key = f"autocomplete:{query.lower()}"

        # Try cache first
        cached_suggestions = await self.redis_client.get_json(cache_key)
        if cached_suggestions:
            logger.info(f"Cache hit for autocomplete: {query}")
            import json

            return json.loads(cached_suggestions)

        logger.info(f"Cache miss for autocomplete: {query}")

        # Get suggestions from database
        suggestions = self.crud.get_product_suggestions(query, limit=10)

        # Cache for 1 hour (3600 seconds)
        if suggestions:
            import json

            await self.redis_client.set_json(
                cache_key, json.dumps(suggestions), ex=3600
            )

        return suggestions

    def add_gallery_image(self, product_id: int, url: str, is_primary: bool = False, alt_text: Optional[str] = None) -> ProductImageResponse:
        self.crud.get_product_by_id(product_id) # ensures product exists
        image = self.crud.add_product_image(product_id, url, is_primary, alt_text)
        return ProductImageResponse.model_validate(image)

    def get_gallery_images(self, product_id: int) -> List[ProductImageResponse]:
        self.crud.get_product_by_id(product_id) # ensures product exists
        images = self.crud.get_product_images(product_id)
        return [ProductImageResponse.model_validate(i) for i in images]

    def delete_gallery_image(self, image_id: int) -> None:
        deleted = self.crud.delete_product_image(image_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Product image not found")

    def add_product_variant(self, product_id: int, variant_dto: ProductVariantCreate) -> ProductVariantResponse:
        self.crud.get_product_by_id(product_id)
        variant = self.crud.add_product_variant(product_id, variant_dto)
        return ProductVariantResponse.model_validate(variant)

    def get_product_variants(self, product_id: int) -> List[ProductVariantResponse]:
        self.crud.get_product_by_id(product_id)
        variants = self.crud.get_product_variants(product_id)
        return [ProductVariantResponse.model_validate(v) for v in variants]

    def update_product_variant(self, variant_id: int, variant_dto: ProductVariantUpdate) -> ProductVariantResponse:
        variant = self.crud.update_product_variant(variant_id, variant_dto)
        if not variant:
            raise HTTPException(status_code=404, detail="Product variant not found")
        return ProductVariantResponse.model_validate(variant)

    def delete_product_variant(self, variant_id: int) -> None:
        deleted = self.crud.delete_product_variant(variant_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Product variant not found")

    from app.schema.product_schema import ProductRelationCreate, ProductRelationResponse

    def add_product_relation(self, product_id: int, relation_dto: 'ProductRelationCreate') -> 'ProductRelationResponse':
        from app.schema.product_schema import ProductRelationResponse
        self.crud.get_product_by_id(product_id)
        self.crud.get_product_by_id(relation_dto.related_product_id)
        relation = self.crud.add_product_relation(product_id, relation_dto)
        return ProductRelationResponse.model_validate(relation)

    def get_product_relations(self, product_id: int) -> List['ProductRelationResponse']:
        from app.schema.product_schema import ProductRelationResponse
        self.crud.get_product_by_id(product_id)
        relations = self.crud.get_product_relations(product_id)
        return [ProductRelationResponse.model_validate(r) for r in relations]

    def delete_product_relation(self, relation_id: int) -> None:
        deleted = self.crud.delete_product_relation(relation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Product relation not found")
