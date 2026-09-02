from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.crud.brand import BrandCrud
from app.schema.brand_schema import BrandCreate, BrandUpdate
from app.models.brand import Brand

class BrandService:
    def __init__(self, db: Session):
        self.crud = BrandCrud(db)

    def create_brand(self, create_dto: BrandCreate) -> Brand:
        return self.crud.create_brand(create_dto)

    def get_all_brands(self) -> list[Brand]:
        return self.crud.get_all_brands()

    def get_brand_by_id(self, brand_id: int) -> Brand:
        brand = self.crud.get_brand_by_id(brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        return brand

    def get_brand_by_slug(self, slug: str) -> Brand:
        brand = self.crud.get_brand_by_slug(slug)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        return brand

    def update_brand(self, brand_id: int, update_dto: BrandUpdate) -> Brand:
        self.get_brand_by_id(brand_id) # ensure exists
        updated = self.crud.update_brand(brand_id, update_dto)
        if not updated:
            raise HTTPException(status_code=404, detail="Brand not found")
        return updated

    def delete_brand(self, brand_id: int) -> None:
        self.get_brand_by_id(brand_id) # ensure exists
        if not self.crud.delete_brand(brand_id):
            raise HTTPException(status_code=400, detail="Could not delete brand")
