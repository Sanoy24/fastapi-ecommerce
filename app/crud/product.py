from pydantic import HttpUrl
from sqlalchemy.orm import Session
from app.schema.product_schema import ProductCreate, ProductUpdate
from app.models.product import Product
from app.core.exceptions import ProductException
from sqlalchemy.exc import IntegrityError
from app.utils.generate_slug import generate_slug, generate_sku
from app.core.logger import logger
from sqlalchemy import select, update, delete


class ProductCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_product(self, create_dto: ProductCreate) -> Product:
        """Create Product"""
        try:
            create_data = create_dto.model_dump()

            if isinstance(create_data.get("image_url"), HttpUrl):
                create_data["image_url"] = str(create_data["image_url"])

            product_name = create_data.get("name")
            if not product_name:
                raise ValueError("Product name is required for slug generation.")

            gen_slug = generate_slug(self.db, product_name)
            gen_sku = generate_sku(product_name)

            product = Product(**create_data, slug=gen_slug, sku=gen_sku)

            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)
            return product
        except IntegrityError as e:
            self.db.rollback()
            logger.info(f"exception: {e}")
            raise ProductException(str(e)) from e

    def get_product_detail(self, slug: str) -> Product:
        stmt = select(Product).where(Product.slug == slug)
        product = self.db.scalar(stmt)
        if not product:
            return None
        return product

    def get_product_by_id(self, id: int) -> Product | None:
        stmt = select(Product).where(Product.id == id)
        return self.db.scalar(stmt)

    def get_all_products(self) -> list[Product]:
        stmt = select(Product).order_by(Product.id)
        return self.db.scalars(stmt).all()

    def update_product(self, id: int, update_dto: ProductUpdate) -> Product | None:
        try:
            update_data = update_dto.model_dump(exclude_unset=True)

            if not update_data:
                return self.get_product_by_id(id)

            if isinstance(update_data.get("image_url"), HttpUrl):
                update_data["image_url"] = str(update_data["image_url"])

            if "name" in update_data:
                update_data["slug"] = generate_slug(self.db, update_data["name"])

            stmt = (
                update(Product)
                .where(Product.id == id)
                .values(**update_data)
                .returning(Product)
            )

            updated = self.db.execute(stmt).scalar_one_or_none()
            self.db.commit()
            return updated
        except IntegrityError as e:
            self.db.rollback()
            raise ProductException(str(e)) from e

    def delete_product(self, id: int) -> bool:
        stmt = delete(Product).where(Product.id == id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True
