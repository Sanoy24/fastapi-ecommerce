"""Shared cart/order pricing logic.

CartService.get_cart_details() (what the customer is shown) and
OrderCrud.create_order() (what they are actually charged) each computed
unit prices, coupon discounts, and promotion discounts independently.
The two implementations drifted: the cart used Product.effective_price
(sale-aware) while checkout used the plain Product.price, and promotions
applied in the cart display were never applied when the order was created.
Both now call these functions so the charged total always matches the
displayed total.
"""
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cart_item import CartItem
from app.models.promotion import Promotion


def get_unit_price(item: CartItem) -> float:
    """Effective per-unit price for a cart item, honoring active product sales."""
    if item.variant_id and item.variant:
        return float(item.variant.price)
    return float(item.product.effective_price)


def calculate_coupon_discount(raw_subtotal: float, coupon) -> float:
    """Discount amount a coupon contributes against raw_subtotal, or 0 if not applicable."""
    if not coupon or not coupon.is_valid:
        return 0.0
    if coupon.min_order_value is not None and raw_subtotal < float(coupon.min_order_value):
        return 0.0
    if coupon.discount_type == "percentage":
        return raw_subtotal * (float(coupon.discount_value) / 100)
    if coupon.discount_type == "fixed":
        return float(coupon.discount_value)
    return 0.0


def calculate_promotion_discount(db: Session, items: List[CartItem]) -> Tuple[float, List[str]]:
    """Evaluate active promotions against the given items.

    Returns (total_discount, applied_promotion_names).
    """
    active_promotions = db.scalars(select(Promotion).where(Promotion.is_active)).all()
    total_discount = 0.0
    applied: List[str] = []

    for promo in active_promotions:
        if promo.type == "percentage_on_category" and promo.conditions and promo.rewards:
            target_cat = promo.conditions.get("category_id")
            discount_pct = promo.rewards.get("discount_percentage", 0)
            if target_cat and discount_pct:
                for item in items:
                    if item.product.category_id == target_cat:
                        price = get_unit_price(item)
                        discount = (price * item.quantity) * (discount_pct / 100)
                        total_discount += discount
                        applied.append(promo.name)

        elif promo.type == "buy_x_get_y" and promo.conditions and promo.rewards:
            target_prod = promo.conditions.get("product_id")
            buy_qty = promo.conditions.get("buy_quantity", 1)
            get_qty = promo.rewards.get("get_quantity", 1)
            if target_prod:
                for item in items:
                    if item.product_id == target_prod and item.quantity >= buy_qty:
                        # Simplification: discount the get_qty
                        price = get_unit_price(item)
                        discount_sets = item.quantity // (buy_qty + get_qty)
                        if discount_sets == 0 and item.quantity > buy_qty:
                            discount_sets = 1
                        discount = discount_sets * get_qty * price
                        total_discount += discount
                        applied.append(promo.name)

    return total_discount, applied
