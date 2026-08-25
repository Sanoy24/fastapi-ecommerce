from pydantic import HttpUrl
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ProductException
from app.core.logger import logger
from app.models.category import Category
from app.models.product import Product
from app.schema.admin_schema import BulkInventoryUpdateItem
from app.schema.common_schema import PaginatedResponse, PaginationLinks, PaginationMeta, CursorPaginatedResponse
from app.schema.product_schema import ProductCreate, ProductResponse, ProductUpdate
from app.schema.product_variant_schema import ProductVariantCreate, ProductVariantUpdate
from app.utils.generate_slug import generate_sku, generate_slug
from typing import List, Literal
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant

allowed_sort_order = Literal["asc", "desc"]
allowed_sort_by = Literal["id", "price", "name", "created_at", "rating", "popularity"]


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
            page: Page number (1-indexed)
            per_page: Items per page (1-100)
            search: Search term for name and description
            category_id: Filter by category
            min_price: Minimum price filter
            max_price: Maximum price filter
            min_rating: Minimum average rating (0-5)
            availability: Filter by stock ('all', 'in_stock', 'out_of_stock')
            sort_by: Field to sort by
            sort_order: Sort direction ('asc' or 'desc')
        """
        logger.info(f"page: {page} - per_page: {per_page}")
        logger.info(
            f"filters - price: [{min_price}, {max_price}], rating: {min_rating}, availability: {availability}"
        )

        page = max(page, 1)
        per_page = max(min(per_page, 100), 1)

        # Base query - only active products
        stmt = select(Product).where(Product.status == "active")

        # Search filter (case-insensitive full-text search)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                Product.name.ilike(search_pattern)
                | Product.description.ilike(search_pattern)
            )

        # Category filter
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)

        # Price range filters
        if min_price is not None:
            stmt = stmt.where(Product.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Product.price <= max_price)

        # Rating filter (using hybrid property)
        if min_rating is not None:
            stmt = stmt.where(Product.average_rating >= min_rating)

        # Availability filter
        if availability == "in_stock":
            stmt = stmt.where(Product.in_stock == True)
        elif availability == "out_of_stock":
            stmt = stmt.where(Product.in_stock == False)
        # 'all' - no filter needed

        # Sorting
        from app.models.order_item import OrderItem

        allowed_sorting_fields = {
            "id": Product.id,
            "name": Product.name,
            "price": Product.price,
            "created_at": Product.created_at,
            "rating": Product.average_rating,
            "popularity": (
                select(func.count(OrderItem.id))
                .where(OrderItem.product_id == Product.id)
                .correlate_except(OrderItem)
                .scalar_subquery()
            ),
        }

        sort_field = allowed_sorting_fields.get(sort_by, Product.id)
        if sort_order == "desc":
            stmt = stmt.order_by(sort_field.desc())
        else:
            stmt = stmt.order_by(sort_field.asc())

        # Count total items matching filters
        count_stmt = stmt.with_only_columns(func.count())
        total_items = self.db.scalar(count_stmt)

        # Pagination
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

        # Build query string for HATEOAS links
        base = "/products"
        query_params = []
        if search:
            query_params.append(f"search={search}")
        if category_id:
            query_params.append(f"category_id={category_id}")
        if min_price is not None:
            query_params.append(f"min_price={min_price}")
        if max_price is not None:
            query_params.append(f"max_price={max_price}")
        if min_rating is not None:
            query_params.append(f"min_rating={min_rating}")
        if availability != "all":
            query_params.append(f"availability={availability}")
        if sort_by != "id":
            query_params.append(f"sort_by={sort_by}")
        if sort_order != "asc":
            query_params.append(f"sort_order={sort_order}")

        query_string = "&".join(query_params)
        base_with_params = f"{base}?{query_string}&" if query_params else f"{base}?"

        links = PaginationLinks(
            self=f"{base_with_params}page={page}&per_page={per_page}",
            first=f"{base_with_params}page=1&per_page={per_page}",
            last=f"{base_with_params}page={total_pages}&per_page={per_page}",
            prev=(
                f"{base_with_params}page={page - 1}&per_page={per_page}"
                if page > 1
                else None
            ),
            next=(
                f"{base_with_params}page={page + 1}&per_page={per_page}"
                if page < total_pages
                else None
            ),
        )

        return PaginatedResponse(
            data=items,
            meta=meta,
            links=links,
        )

    def list_products_cursor(
        self,
        cursor: int | None = None,
        limit: int = 20
    ) -> CursorPaginatedResponse[ProductResponse]:
        """
        Cursor-based pagination for products, ordered by id descending.
        """
        stmt = select(Product).where(Product.status == "active").order_by(Product.id.desc())
        if cursor is not None:
            stmt = stmt.where(Product.id < cursor)
        
        # Fetch limit + 1 to determine if there are more items
        items = self.db.scalars(stmt.limit(limit + 1)).all()
        
        has_more = len(items) > limit
        if has_more:
            items = items[:-1]
            
        next_cursor = items[-1].id if items else None
        
        return CursorPaginatedResponse(
            data=items,
            next_cursor=next_cursor,
            has_more=has_more
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

    def update_product(self, id: int, update_dto: ProductUpdate, admin_id: int | None = None) -> Product | None:
        """Partially update product; auto-generate slug when name changes. Records price history."""
        try:
            update_data = update_dto.model_dump(exclude_unset=True)

            if not update_data:
                return self.get_product_by_id(id)

            if isinstance(update_data.get("image_url"), HttpUrl):
                update_data["image_url"] = str(update_data["image_url"])

            product = self.get_product_by_id(id)
            if not product:
                return None
                
            old_price = float(product.price)
            new_price_val = update_data.get("price")
            new_price = float(new_price_val) if new_price_val is not None else old_price
            
            if new_price != old_price:
                from app.models.price_history import PriceHistory
                history = PriceHistory(
                    product_id=id,
                    old_price=old_price,
                    new_price=new_price,
                    changed_by_id=admin_id
                )
                self.db.add(history)

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

    def get_product_suggestions(self, query: str, limit: int = 10) -> list[str]:
        """
        Get product name suggestions for autocomplete.

        Args:
            query: Search query (minimum 2 characters)
            limit: Maximum number of suggestions (default 10)

        Returns:
            List of product names matching the query
        """
        if not query or len(query) < 2:
            return []

        search_pattern = f"{query}%"  # Prefix matching
        contains_pattern = f"%{query}%"  # Contains matching

        # Get products that start with the query (higher priority)
        stmt_prefix = (
            select(Product.name)
            .where(Product.status == "active")
            .where(Product.name.ilike(search_pattern))
            .distinct()
            .limit(limit)
        )

        prefix_matches = self.db.scalars(stmt_prefix).all()

        # If we have enough prefix matches, return them
        if len(prefix_matches) >= limit:
            return list(prefix_matches)[:limit]

        # Otherwise, get additional matches that contain the query
        remaining = limit - len(prefix_matches)
        stmt_contains = (
            select(Product.name)
            .where(Product.status == "active")
            .where(Product.name.ilike(contains_pattern))
            .where(~Product.name.ilike(search_pattern))  # Exclude prefix matches
            .distinct()
            .limit(remaining)
        )

        contains_matches = self.db.scalars(stmt_contains).all()

        # Combine results: prefix matches first, then contains matches
        return list(prefix_matches) + list(contains_matches)

    def deduct_stock(self, product_id: int, item_quantity: int):
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .with_for_update()
        )
        product = self.db.execute(stmt).scalar_one_or_none()
        if not product:
            raise ProductException(f"Product {product_id} not found")
        if product.stock_quantity < item_quantity:
            raise ProductException(f"Insufficient stock for product {product_id}")
            
        product.stock_quantity -= item_quantity
        self.db.add(product)

    def get_total_products(self):
        total_products = self.db.query(func.count(Product.id)).scalar() or 0
        return total_products

    def total_active_products(self):
        active_products = (
            self.db.query(func.count(Product.id))
            .filter(Product.status == "active")
            .scalar()
            or 0
        )
        return active_products

    def total_inactive_products(self):
        inactive_products = (
            self.db.query(func.count(Product.id))
            .filter(Product.status != "active")
            .scalar()
            or 0
        )
        return inactive_products

    def out_of_stock_count(self):
        out_stock_count = (
            self.db.query(func.count(Product.id))
            .filter(Product.stock_quantity == 0)
            .scalar()
            or 0
        )
        return out_stock_count

    def low_stock_count(self):
        low_stock_count = (
            self.db.query(func.count(Product.id))
            .filter(and_(Product.stock_quantity > 0, Product.stock_quantity < 10))
            .scalar()
            or 0
        )
        return low_stock_count

    def get_slow_stock_products(self, threshold: int):
        products = (
            self.db.query(Product)
            .filter(
                and_(Product.stock_quantity > 0, Product.stock_quantity < threshold)
            )
            .order_by(Product.stock_quantity.asc())
            .all()
        )
        return products

    def bulk_update_inventory(self, updates: List[BulkInventoryUpdateItem]):
        """Bulk update product inventory"""
        updated_count = 0
        failed_products = []

        for update in updates:
            product = (
                self.db.query(Product).filter(Product.id == update.product_id).first()
            )
            if not product:
                failed_products.append(update.product_id)
                continue

            product.stock_quantity = update.stock_quantity
            updated_count += 1

        self.db.commit()

        return updated_count, failed_products

    def add_product_image(self, product_id: int, url: str, is_primary: bool = False, alt_text: str = None) -> ProductImage:
        image = ProductImage(product_id=product_id, url=url, is_primary=is_primary, alt_text=alt_text)
        self.db.add(image)
        self.db.commit()
        self.db.refresh(image)
        return image

    def get_product_images(self, product_id: int) -> list[ProductImage]:
        stmt = select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.display_order)
        return self.db.scalars(stmt).all()

    def delete_product_image(self, image_id: int) -> bool:
        stmt = delete(ProductImage).where(ProductImage.id == image_id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True

    def add_product_variant(self, product_id: int, variant_dto: ProductVariantCreate) -> ProductVariant:
        variant = ProductVariant(product_id=product_id, **variant_dto.model_dump())
        self.db.add(variant)
        try:
            self.db.commit()
            self.db.refresh(variant)
            return variant
        except IntegrityError as e:
            self.db.rollback()
            raise ProductException("Variant sku already exists") from e

    def get_product_variants(self, product_id: int) -> list[ProductVariant]:
        stmt = select(ProductVariant).where(ProductVariant.product_id == product_id)
        return self.db.scalars(stmt).all()

    def update_product_variant(self, variant_id: int, variant_dto: ProductVariantUpdate) -> ProductVariant | None:
        update_data = variant_dto.model_dump(exclude_unset=True)
        if not update_data:
            return self.db.get(ProductVariant, variant_id)

        try:
            stmt = update(ProductVariant).where(ProductVariant.id == variant_id).values(**update_data).returning(ProductVariant)
            updated = self.db.execute(stmt).scalar_one_or_none()
            self.db.commit()
            return updated
        except IntegrityError as e:
            self.db.rollback()
            raise ProductException("Variant update failed due to duplicate sku") from e

    def delete_product_variant(self, variant_id: int) -> bool:
        stmt = delete(ProductVariant).where(ProductVariant.id == variant_id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True

    from app.models.product_relation import ProductRelation

    def add_product_relation(self, product_id: int, relation_dto: 'ProductRelationCreate') -> 'ProductRelation':
        from app.models.product_relation import ProductRelation
        relation = ProductRelation(product_id=product_id, **relation_dto.model_dump())
        self.db.add(relation)
        try:
            self.db.commit()
            self.db.refresh(relation)
            return relation
        except IntegrityError as e:
            self.db.rollback()
            raise ProductException("Failed to add product relation") from e

    def get_product_relations(self, product_id: int) -> list['ProductRelation']:
        from app.models.product_relation import ProductRelation
        stmt = select(ProductRelation).where(ProductRelation.product_id == product_id)
        return self.db.scalars(stmt).all()

    def delete_product_relation(self, relation_id: int) -> bool:
        from app.models.product_relation import ProductRelation
        stmt = delete(ProductRelation).where(ProductRelation.id == relation_id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True
