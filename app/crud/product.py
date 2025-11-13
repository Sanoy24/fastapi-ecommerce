from pydantic import HttpUrl
from sqlalchemy.orm import Session
from app.schema.product_schema import ProductCreate
from app.models.product import Product
from app.core.exceptions import ProductException
from sqlalchemy.exc import IntegrityError
from app.utils.generate_slug import generate_slug, generate_sku
from app.core.logger import logger


class ProductCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_product(self, create_dto: ProductCreate) -> Product:
        try:
            create_data = create_dto.model_dump()

            # 1. FIX: Use 'create_data' to update the 'image_url' value
            #    Note: HttpUrl must be imported if used here.
            if isinstance(create_data.get("image_url"), HttpUrl):
                # Convert the HttpUrl object to a string for the database
                create_data["image_url"] = str(create_data["image_url"])

            # 2. Extract product name and generate slug
            product_name = create_data.get("name")
            if not product_name:
                # Add error handling if the name is missing and required for slug
                raise ValueError("Product name is required for slug generation.")

            gen_slug = generate_slug(self.db, product_name)
            gen_sku = generate_sku(product_name)

            # 3. Create product with all data and the generated slug
            product = Product(**create_data, slug=gen_slug, sku=gen_sku)

            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)
            return product
        except IntegrityError as e:
            self.db.rollback()
            logger.info(f"exception: {e}")
            raise ProductException(str(e)) from e
