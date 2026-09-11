from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.promotion import Promotion
from app.schema.promotion_schema import PromotionCreate, PromotionUpdate


class PromotionCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_promotion(self, data: PromotionCreate) -> Promotion:
        promotion = Promotion(**data.model_dump())
        self.db.add(promotion)
        self.db.commit()
        self.db.refresh(promotion)
        return promotion

    def get_promotion_by_id(self, promotion_id: int) -> Optional[Promotion]:
        return self.db.execute(
            select(Promotion).where(Promotion.id == promotion_id)
        ).scalar_one_or_none()

    def list_promotions(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Promotion]:
        stmt = select(Promotion)
        if active_only:
            stmt = stmt.where(Promotion.is_active)
        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def update_promotion(self, promotion: Promotion, data: PromotionUpdate) -> Promotion:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(promotion, key, value)
        self.db.commit()
        self.db.refresh(promotion)
        return promotion

    def delete_promotion(self, promotion: Promotion) -> None:
        self.db.delete(promotion)
        self.db.commit()
