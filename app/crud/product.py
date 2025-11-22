from pydantic import HttpUrl
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ProductException
from app.core.logger import logger
from app.models.category import Category
from app.models.product import Product
from app.schema.common_schema import PaginatedResponse, PaginationLinks, PaginationMeta
from app.schema.product_schema import ProductCreate, ProductResponse, ProductUpdate
from app.utils.generate_slug import generate_sku, generate_slug
from typing import Literal

allowed_sort_order = Literal["asc", "desc"]
allowed_sort_by = Literal["id", "price", "name", "created_at"]


class ProductCrud:
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

            gen_slug = generate_slug(self.db, product_name, context="product")
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
        result = self.db.scalar(stmt)
        return result

    def get_all_products(
        self,
        page: int = 1,
        per_page: int = 10,
        search: str | None = None,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        sort_by: allowed_sort_by | None = "id",
        sort_order: allowed_sort_by = "asc",
    ) -> PaginatedResponse[ProductResponse]:
        """List all products ordered by id."""
        logger.info(f"page: {page} - per_page: {per_page}")
        logger.warning(f"min price - {min_price} | max price - {max_price}")

        page = max(page, 1)
        per_page = max(min(per_page, 100), 1)

        # base query
        stmt = select(Product).where(Product.is_active == True)

        # filters
        if search:
            stmt = stmt.where(
                Product.name.like(f"%{search}%")
                | Product.description.like(f"%{search}")
            )

        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if min_price:
            stmt = stmt.where(Product.price >= min_price)
        if max_price:
            stmt = stmt.where(Product.price <= max_price)

        # sorting

        allowed_sorting_fields = {
            "id": Product.id,
            "name": Product.name,
            "price": Product.price,
            "created_at": Product.created_at,
        }

        sort_field = allowed_sorting_fields.get(sort_by, Product.id)
        if sort_order == "desc":
            stmt = stmt.order_by(sort_field.desc())
        else:
            stmt = stmt.order_by(sort_field.asc())

        # count total items
        count_stmt = stmt.with_only_columns(func.count())
        total_items = self.db.scalar(count_stmt)

        # total_items = self.db.scalar(
        #     select(func.count()).select_from(Product).where(Product.is_active == True)
        # )

        offset = (page - 1) * per_page

        items = self.db.scalars(stmt.offset(offset).limit(per_page)).all()

        total_pages = (total_items + per_page - 1) // per_page
        from_item = offset + 1 if items else None
        to_item = offset + len(items) if items else None

        meta = PaginationMeta(
            current_page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_items=total_items,
            from_item=from_item,
            to_item=to_item,
        )

        # Generated links (HATEOAS)
        base = "/products"

        links = PaginationLinks(
            self=f"{base}?page={page}&per_page={per_page}",
            first=f"{base}?page=1&per_page={per_page}",
            last=f"{base}?page={total_pages}&per_page={per_page}",
            prev=f"{base}?page={page - 1}&per_page={per_page}" if page > 1 else None,
            next=(
                f"{base}?page={page + 1}&per_page={per_page}"
                if page < total_pages
                else None
            ),
        )

        return PaginatedResponse(
            data=items,
            meta=meta,
            links=links,
        )

    def get_products_by_category_id(self, category_id: int) -> list[Product]:
        stmt = (
            select(Product)
            .where(Product.category_id == category_id)
            .order_by(Product.id)
        )
        return self.db.scalars(stmt).all()

    def get_products_by_category_slug(self, slug: str) -> list[Product]:
        stmt = (
            select(Product)
            .join(Category, Product.category_id == Category.id)
            .where(Category.slug == slug)
            .order_by(Product.id)
        )
        return self.db.scalars(stmt).all()

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

    def deduct_stock(self, product_id: int, item_quantity: int):
        stmt = (
            update(Product)
            .where(Product.id == product_id)
            .values(stock_quantity=Product.stock_quantity - item_quantity)
            .returning(Product.id)
        )
        self.db.execute(stmt).scalar_one_or_none()
