from sqlalchemy.orm import Session
from app.crud.category import CategoryCrud
from app.schema.category_schema import CreateCategory, UpdateCategory, CategoryPublic


class CategoryService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = CategoryCrud(db=db)

    def create_category(create_category_dto: CreateCategory):
        try:
            pass
        except Exception as e:
            pass
