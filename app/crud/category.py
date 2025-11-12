from sqlalchemy.orm import Session
from app.core.exceptions import CategoryCreationError
from app.models.category import Category
from app.schema.category_schema import CategoryPublic, CreateCategory, UpdateCategory
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError


class CategoryCrud:
    def __init__(self, db: Session):
        self.db = db

    # create category
    # crud.py

    def create_category(self, create_dto: CreateCategory) -> Category:
        try:
            category_data = create_dto.model_dump()
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
        """Retrieves a Category by its primary key (id)."""
        stmt = select(Category).where(Category.id == id)
        return self.db.scalar(stmt)

    def get_category_by_slug(self, slug: str):
        """Retrieves a Category by its unique slug."""
        stmt = select(Category).where(Category.slug == slug)
        return self.db.scalar(stmt)

    def update_category(self, id: int, update_dto: UpdateCategory) -> Category:
        """Updates an existing Category record efficiently."""
        update_data = update_dto.model_dump(exclude_unset=True)

        if not update_data:
            return self.get_category_by_id(id)

        stmt = (
            update(Category)
            .where(Category.id == id)
            .values(**update_data)
            .returning(Category)
        )

        updated_category = self.db.execute(stmt).scalar_one_or_none()
        self.db.commit()
        return updated_category

    # delete category
    def delete_category(self, id: int) -> bool:
        """Deletes a Category record."""
        stmt = delete(Category).where(Category.id == id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True

    def get_all_categories(self) -> list[Category]:
        """Get all categories"""
        stmt = select(Category).order_by(Category.id)
        result = self.db.scalars(stmt).all()
        return result
