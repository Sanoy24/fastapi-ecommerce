from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from typing import Sequence
from sqlalchemy.exc import IntegrityError
from app.models.brand import Brand
from app.schema.brand_schema import BrandCreate, BrandUpdate
from app.utils.generate_slug import generate_slug
from app.core.exceptions import BrandException

class BrandCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_brand(self, create_dto: BrandCreate) -> Brand:
        try:
            brand_data = create_dto.model_dump()
            slug = generate_slug(self.db, brand_data["name"], "brand")
            brand_data["slug"] = slug

            brand = Brand(**brand_data)
            self.db.add(brand)
            self.db.commit()
            self.db.refresh(brand)
            return brand
        except IntegrityError as e:
            self.db.rollback()
            raise BrandException(str(e)) from e

    def get_brand_by_id(self, brand_id: int) -> Brand | None:
        stmt = select(Brand).where(Brand.id == brand_id)
        return self.db.scalar(stmt)

    def get_brand_by_slug(self, slug: str) -> Brand | None:
        stmt = select(Brand).where(Brand.slug == slug)
        return self.db.scalar(stmt)

    def get_all_brands(self) -> Sequence[Brand]:
        stmt = select(Brand).order_by(Brand.name)
        return self.db.scalars(stmt).all()

    def update_brand(self, brand_id: int, update_dto: BrandUpdate) -> Brand | None:
        update_data = update_dto.model_dump(exclude_unset=True)
        if not update_data:
            return self.get_brand_by_id(brand_id)

        try:
            if "name" in update_data:
                update_data["slug"] = generate_slug(self.db, update_data["name"], "brand")

            stmt = update(Brand).where(Brand.id == brand_id).values(**update_data).returning(Brand)
            updated = self.db.execute(stmt).scalar_one_or_none()
            self.db.commit()
            return updated
        except IntegrityError as e:
            self.db.rollback()
            raise BrandException("Brand update failed due to duplicate name.") from e

    def delete_brand(self, brand_id: int) -> bool:
        stmt = delete(Brand).where(Brand.id == brand_id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            return False
        self.db.commit()
        return True
