from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.promotion_crud import PromotionCrud
from app.schema.promotion_schema import (
    PromotionCreate,
    PromotionResponse,
    PromotionUpdate,
    validate_date_window,
    validate_promotion_shape,
)


class PromotionService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = PromotionCrud(db)

    def _validate_referenced_entities(self, promo_type: str, conditions: dict) -> None:
        """conditions.category_id / .product_id are checked for *shape* by
        the schema; only a DB query can confirm they actually exist. A
        dangling reference wouldn't error anywhere else — the promotion
        would just never match any cart item and silently never apply,
        which is exactly the quiet failure this should catch up front.
        """
        if promo_type == "percentage_on_category":
            from app.models.category import Category
            category_id = conditions["category_id"]
            if not self.db.get(Category, category_id):
                raise HTTPException(status_code=400, detail=f"Category {category_id} does not exist")
        elif promo_type == "buy_x_get_y":
            from app.models.product import Product
            product_id = conditions["product_id"]
            if not self.db.get(Product, product_id):
                raise HTTPException(status_code=400, detail=f"Product {product_id} does not exist")

    def create_promotion(self, data: PromotionCreate) -> PromotionResponse:
        self._validate_referenced_entities(data.type, data.conditions)
        promotion = self.crud.create_promotion(data)
        return PromotionResponse.model_validate(promotion)

    def get_promotion(self, promotion_id: int) -> PromotionResponse:
        promotion = self.crud.get_promotion_by_id(promotion_id)
        if not promotion:
            raise HTTPException(status_code=404, detail="Promotion not found")
        return PromotionResponse.model_validate(promotion)

    def list_promotions(
        self, skip: int = 0, limit: int = 100, active_only: bool = False
    ) -> List[PromotionResponse]:
        return [
            PromotionResponse.model_validate(p)
            for p in self.crud.list_promotions(skip, limit, active_only)
        ]

    def update_promotion(self, promotion_id: int, data: PromotionUpdate) -> PromotionResponse:
        promotion = self.crud.get_promotion_by_id(promotion_id)
        if not promotion:
            raise HTTPException(status_code=404, detail="Promotion not found")

        # Re-validate the full merged shape — a partial update (e.g. just
        # flipping is_active) must not leave conditions/rewards internally
        # inconsistent with type, or introduce an invalid date window.
        merged_type = data.type or promotion.type
        merged_conditions = data.conditions if data.conditions is not None else (promotion.conditions or {})
        merged_rewards = data.rewards if data.rewards is not None else (promotion.rewards or {})
        merged_starts_at = data.starts_at if data.starts_at is not None else promotion.starts_at
        merged_ends_at = data.ends_at if data.ends_at is not None else promotion.ends_at

        try:
            validate_promotion_shape(merged_type, merged_conditions, merged_rewards)
            validate_date_window(merged_starts_at, merged_ends_at)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        self._validate_referenced_entities(merged_type, merged_conditions)

        updated = self.crud.update_promotion(promotion, data)
        return PromotionResponse.model_validate(updated)

    def delete_promotion(self, promotion_id: int) -> None:
        promotion = self.crud.get_promotion_by_id(promotion_id)
        if not promotion:
            raise HTTPException(status_code=404, detail="Promotion not found")
        self.crud.delete_promotion(promotion)
