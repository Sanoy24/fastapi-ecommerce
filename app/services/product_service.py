from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import ProductException
from app.core.logger import logger
from app.crud.category import CategoryCrud
from app.crud.product import ProductCrud
from app.schema.product_schema import ProductCreate, ProductResponse, ProductUpdate


class ProductService:
    def __init__(self, db: Session):
        self.db = db
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

    def get_product_by_id(self, id: int) -> ProductResponse:
        """Retrieve a product by id; 404 if not found."""
        product = self.crud.get_product_by_id(id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )
        return ProductResponse.model_validate(product)

    def get_all_products(self) -> List[ProductResponse]:
        """List all products as response models."""
        try:
            products = self.crud.get_all_products()
            return [ProductResponse.model_validate(p) for p in products]
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
