from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError  # Import for specific handling
from app.core.exceptions import CategoryCreationError, CategoryUpdateError
from app.crud.category import CategoryCrud
from app.schema.category_schema import CreateCategory, UpdateCategory, CategoryPublic
from fastapi import HTTPException, status
from app.core.logger import logger


class CategoryService:
    """Business logic for categories including validation and error mapping."""

    def __init__(self, db: Session):
        self.db = db
        self.crud = CategoryCrud(db=db)

    def create_category(self, create_dto: CreateCategory) -> CategoryPublic:
        """Create a category and return a validated response model."""
        try:
            result = self.crud.create_category(create_dto)
            return CategoryPublic.model_validate(result)
        except CategoryCreationError as e:
            logger.warning(f"error: {e}")
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=409, detail="Category already exists.")
            raise HTTPException(status_code=400, detail="Invalid category data.")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    def get_category_by_id(self, id: int) -> CategoryPublic:
        """Retrieve a category by id; 404 if missing."""
        category = self.crud.get_category_by_id(id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        return CategoryPublic.model_validate(category)

    def get_all_categories(self) -> list[CategoryPublic]:
        """List all categories as response models."""
        try:
            categories = self.crud.get_all_categories()
            return [CategoryPublic.model_validate(cat) for cat in categories]
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch categories.",
            )

    def get_category_by_slug(self, slug: str) -> CategoryPublic:
        """Retrieve a category by slug; 404 if missing."""
        category = self.crud.get_category_by_slug(slug)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        return CategoryPublic.model_validate(category)

    def update_category(self, id: int, update_dto: UpdateCategory) -> CategoryPublic:
        """Partially update a category and return a validated response model."""
        try:
            updated_category = self.crud.update_category(id, update_dto)
            if not updated_category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
                )
            return CategoryPublic.model_validate(updated_category)
        except CategoryUpdateError as e:
            if "its own parent" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid category update data",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="please try again.",
            )

    def delete_category(self, id: int) -> None:
        """Delete a category by id; 404 if missing."""
        is_deleted = self.crud.delete_category(id)
        if not is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        return None
