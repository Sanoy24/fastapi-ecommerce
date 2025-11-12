from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError  # Import for specific handling
from app.core.exceptions import CategoryCreationError
from app.crud.category import CategoryCrud
from app.schema.category_schema import CreateCategory, UpdateCategory, CategoryPublic
from fastapi import HTTPException, status
from app.core.logger import logger


class CategoryService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = CategoryCrud(db=db)

    def create_category(self, create_dto: CreateCategory) -> CategoryPublic:
        try:
            result = self.crud.create_category(create_dto)
            return CategoryPublic.model_validate(result)
        except CategoryCreationError as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=409, detail="Category already exists.")
            raise HTTPException(status_code=400, detail="Invalid category data.")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    def get_category_by_id(self, id: int) -> CategoryPublic:
        category = self.crud.get_category_by_id(id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        return CategoryPublic.model_validate(category)

    def get_category_by_slug(self, slug: str) -> CategoryPublic:
        category = self.crud.get_category_by_slug(slug)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        return CategoryPublic.model_validate(category)

    def update_category(self, id: int, update_dto: UpdateCategory) -> CategoryPublic:
        updated_category = self.crud.update_category(id, update_dto)
        if not updated_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        return CategoryPublic.model_validate(updated_category)

    def delete_category(
        self, id: int
    ) -> None:  # Change hint to None (or dict if you want a message)
        is_deleted = self.crud.delete_category(id)
        if not is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        return None
