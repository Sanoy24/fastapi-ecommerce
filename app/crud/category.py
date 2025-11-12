from sqlalchemy.orm import Session
from app.models.category import Category
from app.schema.category_schema import CategoryPublic, CreateCategory, UpdateCategory


class CategoryCrud:
    def __init__(self, db: Session):
        self.db = db

    # create category
    def create_category(self, create_category_dto: CreateCategory) -> Category:
        category_data = create_category_dto.model_dump()
        category = Category(**category_data)
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    # get category
    def get_category(self, id: str):
        return self.db.query(Category).filter(Category.id == id).first()

    def get_category_dto(self, slug: str):
        return self.db.query(Category).filter(Category.slug == slug).first()

    # delete category
    def delete_category(self, id: int):
        category = self.get_category(id)
        if not category:
            return False
        self.db.delete(category)
        self.db.commit()
        return True
