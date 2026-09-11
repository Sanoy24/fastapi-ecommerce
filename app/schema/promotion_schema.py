import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

PromotionType = Literal["buy_x_get_y", "free_shipping", "percentage_on_category"]


def validate_promotion_shape(promo_type: str, conditions: dict, rewards: dict) -> None:
    """Validate conditions/rewards match what promo_type actually needs.

    This is exactly what app/services/pricing.py's
    calculate_promotion_discount and qualifies_for_free_shipping read via
    .get() — a malformed promotion here previously wouldn't error, it
    would just silently never apply any discount at checkout. Shared
    between create (via the model_validator below) and update (see
    PromotionService.update_promotion, which re-validates the full merged
    shape since a partial update must not leave it inconsistent).
    """
    if promo_type == "percentage_on_category":
        if not isinstance(conditions.get("category_id"), int):
            raise ValueError("percentage_on_category requires conditions.category_id (int)")
        pct = rewards.get("discount_percentage")
        if not isinstance(pct, (int, float)) or isinstance(pct, bool) or not (0 < pct <= 100):
            raise ValueError("percentage_on_category requires rewards.discount_percentage between 0 and 100")

    elif promo_type == "buy_x_get_y":
        if not isinstance(conditions.get("product_id"), int):
            raise ValueError("buy_x_get_y requires conditions.product_id (int)")
        buy_qty = conditions.get("buy_quantity", 1)
        if not isinstance(buy_qty, int) or isinstance(buy_qty, bool) or buy_qty < 1:
            raise ValueError("buy_x_get_y's conditions.buy_quantity must be a positive integer")
        get_qty = rewards.get("get_quantity")
        if not isinstance(get_qty, int) or isinstance(get_qty, bool) or get_qty < 1:
            raise ValueError("buy_x_get_y requires rewards.get_quantity (positive int)")

    elif promo_type == "free_shipping":
        min_order_value = conditions.get("min_order_value")
        if min_order_value is not None:
            if not isinstance(min_order_value, (int, float)) or isinstance(min_order_value, bool) or min_order_value < 0:
                raise ValueError("free_shipping's conditions.min_order_value must be a non-negative number")


def validate_date_window(starts_at: Optional[datetime.datetime], ends_at: Optional[datetime.datetime]) -> None:
    if starts_at and ends_at and starts_at >= ends_at:
        raise ValueError("starts_at must be before ends_at")


class PromotionBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    type: PromotionType
    conditions: dict = Field(default_factory=dict)
    rewards: dict = Field(default_factory=dict)
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    is_active: bool = True

    @model_validator(mode="after")
    def _validate(self) -> "PromotionBase":
        try:
            validate_promotion_shape(self.type, self.conditions, self.rewards)
            validate_date_window(self.starts_at, self.ends_at)
        except ValueError as e:
            raise ValueError(str(e)) from e
        return self


class PromotionCreate(PromotionBase):
    pass


class PromotionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    type: Optional[PromotionType] = None
    conditions: Optional[dict] = None
    rewards: Optional[dict] = None
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    is_active: Optional[bool] = None

    model_config = {"from_attributes": True}


class PromotionResponse(BaseModel):
    id: int
    name: str
    type: str
    conditions: Optional[dict] = None
    rewards: Optional[dict] = None
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    is_active: bool

    model_config = {"from_attributes": True}
