from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import ProductException
from app.core.logger import logger
from app.core.redis import RedisClient
from app.crud.category import CategoryCrud
from app.crud.product import ProductCrud
from app.schema.product_schema import ProductCreate, ProductResponse, ProductUpdate
from app.schema.common_schema import PaginatedResponse


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
        page: Optional[int],
        per_page: Optional[int],
        search: str | None = None,
        category_id: int | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        min_rating: float | None = None,
        availability: str | None = "all",
        sort_by: str | None = "id",
        sort_order: str | None = "asc",
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
