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
from typing import TYPE_CHECKING, List, Optional, Protocol, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cart_item import CartItem
from app.models.promotion import Promotion

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.product_variant import ProductVariant


class LineItemLike(Protocol):
    """Structural shape get_unit_price (and _calculate_tax_amount /
    _create_order_items_and_reserve_stock in app/crud/order.py) actually
    need — satisfied by a real CartItem, and by the plain (non-ORM) object
    OrderCrud.create_renewal_order builds for a subscription's line item,
    which has no cart to belong to."""

    product_id: int
    variant_id: Optional[int]
    quantity: int
    product: "Product"
    variant: Optional["ProductVariant"]


def get_unit_price(item: LineItemLike) -> float:
    """Effective per-unit price for a line item, honoring active product sales."""
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


def calculate_points_discount(raw_subtotal: float, points_redeemed: int) -> float:
    """Discount from redeeming points_redeemed at
    settings.POINTS_REDEMPTION_VALUE per point, capped at raw_subtotal so a
    redemption alone can never make a cart/order total negative (stacking
    with a coupon/promotion discount is still capped at the call site, the
    same way calculate_coupon_discount's result is)."""
    if points_redeemed <= 0:
        return 0.0
    return min(raw_subtotal, points_redeemed * settings.POINTS_REDEMPTION_VALUE)


def calculate_promotion_discount(db: Session, items: List[CartItem]) -> Tuple[float, List[str]]:
    """Evaluate active promotions against the given items.

    Returns (total_discount, applied_promotion_names).
    """
    candidate_promotions = db.scalars(select(Promotion).where(Promotion.is_active)).all()
    total_discount = 0.0
    applied: List[str] = []

    for promo in candidate_promotions:
        # is_active is checked above at the DB level as a cheap prefilter,
        # but starts_at/ends_at were never checked at all until is_valid
        # existed — a promotion scheduled for the future, or already
        # expired, applied at checkout today regardless.
        if not promo.is_valid:
            continue

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


def qualifies_for_free_shipping(db: Session, raw_subtotal: float) -> bool:
    """Whether any active, currently-valid free_shipping promotion applies.

    "free_shipping" has been a valid Promotion.type since the enum was
    defined, but calculate_promotion_discount above only ever handled
    percentage_on_category and buy_x_get_y — a free_shipping promotion
    could be created and would silently do nothing at checkout. Called
    from OrderCrud._calculate_shipping_amount.
    """
    promotions = db.scalars(
        select(Promotion).where(Promotion.type == "free_shipping", Promotion.is_active)
    ).all()
    for promo in promotions:
        if not promo.is_valid:
            continue
        min_order_value = (promo.conditions or {}).get("min_order_value")
        if min_order_value is None or raw_subtotal >= float(min_order_value):
            return True
    return False
