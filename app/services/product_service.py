from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.crud.product import ProductCrud
from app.schema.product_schema import ProductCreate, ProductResponse
from app.core.exceptions import ProductException
from app.core.logger import logger


class ProductService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = ProductCrud(db=db)

    def create_product(self, create_dto: ProductCreate) -> ProductResponse:
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
