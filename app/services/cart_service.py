from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.cart import Cart
from app.models.coupon import Coupon
from app.schema.cart_schema import CartItemCreate, CartItemUpdate
from app.core.logger import logger
from app.core.exceptions import ProductException
from app.crud.product import ProductCrud
from app.crud.cart_item import CartCrud
from app.services.pricing import (
    calculate_coupon_discount,
    calculate_points_discount,
    calculate_promotion_discount,
    calculate_store_credit_discount,
    get_unit_price,
)


class CartService:
    def __init__(self, db: Session):
        self.db = db
        self.cart_crud = CartCrud(db=db)
        self.prod_crud = ProductCrud(db=db)

    def get_or_create_cart(self, user_id: Optional[int], session_id: Optional[str]):
        try:
            if user_id:
                cart = self.cart_crud.get_cart_by_user_id(user_id=user_id)
                if cart:
                    return cart
                cart = self.cart_crud.create_cart_by_user_id(user_id=user_id)
                return cart
            else:
                if not session_id:
                    raise ValueError("session_id is required when user_id is not provided")
                cart = self.cart_crud.get_cart_by_session_id(session_id=session_id)
                if cart:
                    return cart
                cart = self.cart_crud.create_cart_by_session_id(session_id=session_id)
                return cart
        except Exception as e:
            logger.info(f"exception: {e}")

    def add_item(self, cart: Cart, data: CartItemCreate):
        product = self.prod_crud.get_product_by_id(data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="product not found")

        if data.variant_id:
            from app.models.product_variant import ProductVariant
            variant = self.db.scalar(select(ProductVariant).where(ProductVariant.id == data.variant_id))
            if not variant or variant.product_id != product.id:
                raise HTTPException(status_code=404, detail="Variant not found")
            if variant.stock_quantity < data.quantity:
                raise ProductException("Variant out of stock")
        else:
            if product.stock_quantity < data.quantity:
                raise ProductException("Product out of stock")

        existing = self.cart_crud.get_cart_item_by_product(cart.id, product.id, data.variant_id)

        if existing:
            result = self.cart_crud.update_existing_cart_item(
                cart.id, product.id, data.quantity, data.variant_id
            )
            return result

        new_item = self.cart_crud.add_new_cart_item(
            cart_id=cart.id, product_id=product.id, quantity=data.quantity, variant_id=data.variant_id
        )
        return new_item

    def update_item(self, cart: Cart, item_id: int, data: CartItemUpdate):
        item = self.cart_crud.update_item(cart_id=cart.id, item_id=item_id, data=data)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
            )
        return item

    def remove_item(self, cart: Cart, item_id: int):
        item = self.cart_crud.remove_item(cart_id=cart.id, item_id=item_id)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
            )
        return item

    def get_cart_details(self, cart: Cart):
        items = []

        raw_subtotal = sum(item.quantity * get_unit_price(item) for item in cart.cart_items)

        coupon = cart.coupon
        if cart.coupon_id and not coupon:
            from app.models.coupon import Coupon
            coupon = self.db.execute(select(Coupon).where(Coupon.id == cart.coupon_id)).scalar_one_or_none()

        coupon_discount = calculate_coupon_discount(raw_subtotal, coupon)
        promo_discount, applied_promotions = calculate_promotion_discount(self.db, list(cart.cart_items))
        points_discount = calculate_points_discount(raw_subtotal, cart.points_redeemed)
        store_credit_discount = calculate_store_credit_discount(raw_subtotal, float(cart.store_credit_applied))

        subtotal = max(
            0.0, raw_subtotal - coupon_discount - promo_discount - points_discount - store_credit_discount
        )

        total_items = sum(item.quantity for item in cart.cart_items)

        for item in cart.cart_items:
            product = item.product
            price = get_unit_price(item)
            item_sub = price * item.quantity

            name = product.name
            if item.variant_id and item.variant:
                name = f"{product.name} - {item.variant.name}"

            items.append(
                {
                    "id": item.id,
                    "product_id": product.id,
                    "variant_id": item.variant_id,
                    "quantity": item.quantity,
                    "product_name": name,
                    "unit_price": price,
                    "subtotal": item_sub,
                }
            )

        # Calculate estimated tax
        from app.models.tax_rate import TaxRate
        from app.models.address import Address

        estimated_tax = 0.0
        tax_rates = self.db.scalars(select(TaxRate).where(TaxRate.is_active)).all()

        # Try to find user's region
        region = None
        if cart.user_id:
            default_addr = self.db.execute(
                select(Address).where(Address.user_id == cart.user_id, Address.is_default)
            ).scalar_one_or_none()
            if default_addr:
                region = default_addr.state or default_addr.country

        for item in cart.cart_items:
            product = item.product
            price = get_unit_price(item)
            item_tax = 0.0
            for tr in tax_rates:
                if tr.applies_to == "all":
                    item_tax += price * float(tr.rate)
                elif tr.applies_to == "category" and tr.category_id == product.category_id:
                    item_tax += price * float(tr.rate)
                elif region and tr.applies_to == "region" and (tr.region and tr.region.lower() == region.lower()):
                    item_tax += price * float(tr.rate)
            estimated_tax += item_tax * item.quantity

        estimated_tax = round(estimated_tax, 2)
        total_amount = round(subtotal + estimated_tax, 2)

        # subtotal/estimated_tax/total_amount above are always in
        # settings.BASE_CURRENCY_CODE (every Product price is) —
        # display_* below is the same figures converted into whatever
        # currency the customer picked via PUT /cart/currency, so the
        # frontend can show one number consistently regardless of whether
        # a non-base currency was ever selected.
        from app.core.config import settings
        from app.crud.currency import CurrencyCrud
        from app.utils.currency import convert_from_base

        currency_code = settings.BASE_CURRENCY_CODE
        exchange_rate = 1.0
        if cart.currency_code:
            currency = CurrencyCrud(self.db).get_active(cart.currency_code)
            if currency:
                currency_code = currency.code
                exchange_rate = float(currency.exchange_rate_to_base)

        return {
            "id": cart.id,
            "items": items,
            "total_items": total_items,
            "subtotal": raw_subtotal,
            "coupon_code": cart.coupon.code if cart.coupon else None,
            "discount_amount": raw_subtotal - subtotal,
            "estimated_tax": estimated_tax,
            "total_amount": total_amount,
            "applied_promotions": applied_promotions,
            "points_redeemed": cart.points_redeemed,
            "points_discount_amount": points_discount,
            "loyalty_points_balance": cart.user.loyalty_points_balance if cart.user_id else 0,
            "store_credit_applied": float(cart.store_credit_applied),
            "store_credit_discount_amount": store_credit_discount,
            "store_credit_balance": float(cart.user.store_credit_balance) if cart.user_id else 0.0,
            "currency_code": currency_code,
            "exchange_rate_to_base": exchange_rate,
            "display_subtotal": convert_from_base(raw_subtotal, exchange_rate, currency_code),
            "display_total_amount": convert_from_base(total_amount, exchange_rate, currency_code),
        }

    def apply_coupon(self, cart: Cart, code: str) -> Cart:
        coupon = self.db.execute(select(Coupon).where(Coupon.code == code)).scalar_one_or_none()
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")

        if not coupon.is_valid:
            raise HTTPException(status_code=400, detail="Coupon is invalid, expired, or usage limit reached")

        raw_subtotal = sum(item.quantity * get_unit_price(item) for item in cart.cart_items)
        if coupon.min_order_value and raw_subtotal < float(coupon.min_order_value):
            raise HTTPException(status_code=400, detail=f"Minimum order value of {coupon.min_order_value} required")

        cart.coupon_id = coupon.id
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def remove_coupon(self, cart: Cart) -> Cart:
        cart.coupon_id = None
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def redeem_points(self, cart: Cart, available_balance: int, points: int) -> Cart:
        """Set how many loyalty points to redeem toward this cart's total.

        available_balance comes from the caller's already-loaded User (see
        cart.py) rather than being looked up here — it's re-validated again
        against the live balance at checkout (OrderCrud._calculate_discount)
        regardless, since a customer can sit on a cart for a while before
        placing the order.
        """
        if points <= 0:
            raise HTTPException(status_code=400, detail="Points must be positive")
        if points > available_balance:
            raise HTTPException(
                status_code=400, detail=f"Insufficient loyalty points balance: you have {available_balance}"
            )

        cart.points_redeemed = points
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def remove_points(self, cart: Cart) -> Cart:
        cart.points_redeemed = 0
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def apply_store_credit(self, cart: Cart, available_balance: float, amount: float) -> Cart:
        """Set how much store credit to apply toward this cart's total.
        Re-validated against the live balance again at checkout, the same
        as redeem_points above."""
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        if amount > available_balance:
            raise HTTPException(
                status_code=400, detail=f"Insufficient store credit balance: you have {available_balance:.2f}"
            )

        cart.store_credit_applied = amount
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def remove_store_credit(self, cart: Cart) -> Cart:
        cart.store_credit_applied = 0
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def set_currency(self, cart: Cart, currency_code: str) -> Cart:
        from app.crud.currency import CurrencyCrud

        currency = CurrencyCrud(self.db).get_active(currency_code)
        if not currency:
            raise HTTPException(status_code=404, detail=f"Currency '{currency_code.upper()}' not found or inactive")

        cart.currency_code = currency.code
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def clear_currency(self, cart: Cart) -> Cart:
        """Back to the base currency."""
        cart.currency_code = None
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def merge_carts(self, user_id: int, session_id: Optional[str]):
        if not session_id:
            return

        user_cart = self.cart_crud.get_cart_by_user_id(user_id=user_id)
        anon_cart = self.cart_crud.get_cart_by_session_id(session_id=session_id)

        logger.info(f"info user cart: {user_cart}")
        logger.info(f"anon cart: {anon_cart}")

        if not anon_cart:
            return

        if not user_cart:
            self.cart_crud.update_anon_cart_to_user_cart(
                user_id=user_id, session_id=session_id
            )
            return

        for item in anon_cart.cart_items:
            existing = self.cart_crud.get_cart_item_by_product(
                user_cart.id, item.product_id, item.variant_id
            )

            if existing:
                existing.quantity += item.quantity
            else:
                item.cart_id = user_cart.id
        self.cart_crud.remove_anon_cart(session_id=session_id)
