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
    """Data access layer for Product entities.

    Provides create, read, update, and delete operations using SQLAlchemy 2.0
    queries and handles uniqueness conflicts via ProductException.
    """
    def __init__(self, db: Session):
        self.db = db

    def create_product(self, create_dto: ProductCreate) -> Product:
        """Create a new product with generated slug and sku."""
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
        """Retrieve a product by slug; returns None if not found."""
        stmt = select(Product).where(Product.slug == slug)
        product = self.db.scalar(stmt)
        if not product:
            return None
        return product

    def get_product_by_id(self, id: int) -> Product | None:
        """Retrieve a product by id; returns None if not found."""
        stmt = select(Product).where(Product.id == id)
        return self.db.scalar(stmt)

    def get_all_products(self) -> list[Product]:
        """List all products ordered by id."""
        stmt = select(Product).order_by(Product.id)
        return self.db.scalars(stmt).all()

<<<<<<< Updated upstream
=======
    def get_products_by_category_id(self, category_id: int) -> list[Product]:
        """List products filtered by category id."""
        stmt = (
            select(Product)
            .where(Product.category_id == category_id)
            .order_by(Product.id)
        )
        return self.db.scalars(stmt).all()

    def get_products_by_category_slug(self, slug: str) -> list[Product]:
        """List products in the category identified by slug."""
        stmt = (
            select(Product)
            .join(Category, Product.category_id == Category.id)
            .where(Category.slug == slug)
            .order_by(Product.id)
        )
        return self.db.scalars(stmt).all()

>>>>>>> Stashed changes
    def update_product(self, id: int, update_dto: ProductUpdate) -> Product | None:
        """Partially update product; auto-generate slug when name changes."""
        try:
            update_data = update_dto.model_dump(exclude_unset=True)

            if not update_data:
                return self.get_product_by_id(id)

            if isinstance(update_data.get("image_url"), HttpUrl):
                update_data["image_url"] = str(update_data["image_url"])

            if "name" in update_data and "slug" not in update_data:
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
        """Delete product by id. Returns True if deleted else False."""
        stmt = delete(Product).where(Product.id == id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True
