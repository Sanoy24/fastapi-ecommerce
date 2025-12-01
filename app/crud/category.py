from pydantic import HttpUrl
from sqlalchemy.orm import Session
from app.core.exceptions import CategoryCreationError, CategoryUpdateError
from app.models.category import Category
from app.schema.category_schema import CategoryPublic, CreateCategory, UpdateCategory
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from app.core.logger import logger
from app.utils.generate_slug import generate_slug


class CategoryCrud:
    """Data access layer for Category entities."""

    def __init__(self, db: Session):
        self.db = db

    # create category
    # crud.py

    def create_category(self, create_dto: CreateCategory) -> Category:
        """Create a new category and return the persisted model."""
        try:
            category_data = create_dto.model_dump()

            if isinstance(category_data.get("image_url"), HttpUrl):
                category_data["image_url"] = str(category_data["image_url"])

            slug = generate_slug(self.db, category_data["name"], "category")

            category_data["slug"] = slug
            category = Category(**category_data)
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
            return category
        except IntegrityError as e:
            self.db.rollback()
            raise CategoryCreationError(str(e)) from e

    # get category
    def get_category_by_id(self, id: int) -> Category | None:
        """Retrieve a category by primary key (id). Returns None if missing."""
        stmt = select(Category).where(Category.id == id)
        return self.db.scalar(stmt)

    def get_category_by_slug(self, slug: str):
        """Retrieve a category by unique slug."""
        stmt = select(Category).where(Category.slug == slug)
        return self.db.scalar(stmt)

    def update_category(self, id: int, update_dto: UpdateCategory) -> Category:
        """Partially update a category; returns the updated model."""
        try:
            update_data = update_dto.model_dump(exclude_unset=True)

            if "parent_id" in update_data and update_data["parent_id"] == id:
                raise CategoryUpdateError("A category cannot be its own parent")

            if not update_data:
                return self.get_category_by_id(id)

            stmt = (
                update(Category)
                .where(Category.id == id)
                .values(**update_data)
                .returning(Category)  # This ensures the returned object is complete
            )

            updated_category = self.db.execute(stmt).scalar_one_or_none()
            self.db.commit()

            # --- REMOVE THIS LINE ---
            # self.db.refresh(updated_category)
            logger.info(f"--------: {updated_category}")

            return updated_category
        except ValueError as e:
            raise CategoryUpdateError(str(e)) from e

    # delete category
    def delete_category(self, id: int) -> bool:
        """Delete a category by id. Returns True if deleted else False."""
        stmt = delete(Category).where(Category.id == id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True

    def get_all_categories(self) -> list[Category]:
        """List all categories ordered by id."""
        stmt = select(Category).order_by(Category.id)
        result = self.db.scalars(stmt).all()
        return result
