from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.coupon import Coupon
from app.schema.cart_schema import CartItemCreate, CartItemUpdate
from app.core.logger import logger
from app.core.exceptions import ProductException
from app.crud.product import ProductCrud
from app.crud.cart_item import CartCrud


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
        def _get_price(item: CartItem) -> float:
            if item.variant_id and item.variant:
                return float(item.variant.price)
            return float(item.product.price)
            
        raw_subtotal = sum(item.quantity * _get_price(item) for item in cart.cart_items)
        subtotal = raw_subtotal
        
        coupon = cart.coupon
        if cart.coupon_id and not coupon:
            from app.models.coupon import Coupon
            coupon = self.db.execute(select(Coupon).where(Coupon.id == cart.coupon_id)).scalar_one_or_none()

        if coupon:
            if coupon.is_valid and (coupon.min_order_value is None or raw_subtotal >= float(coupon.min_order_value)):
                if coupon.discount_type == "percentage":
                    discount = raw_subtotal * (float(coupon.discount_value) / 100)
                    subtotal -= discount
                elif coupon.discount_type == "fixed":
                    subtotal -= float(coupon.discount_value)
            
            if subtotal < 0:
                subtotal = 0.0
                
        # Evaluate Promotions
        from app.models.promotion import Promotion
        active_promotions = self.db.scalars(
            select(Promotion).where(Promotion.is_active)
        ).all()
        
        applied_promotions = []
        for promo in active_promotions:
            if promo.type == "percentage_on_category" and promo.conditions and promo.rewards:
                target_cat = promo.conditions.get("category_id")
                discount_pct = promo.rewards.get("discount_percentage", 0)
                if target_cat and discount_pct:
                    for item in cart.cart_items:
                        if item.product.category_id == target_cat:
                            price = _get_price(item)
                            discount = (price * item.quantity) * (discount_pct / 100)
                            subtotal -= discount
                            applied_promotions.append(promo.name)
            
            elif promo.type == "buy_x_get_y" and promo.conditions and promo.rewards:
                target_prod = promo.conditions.get("product_id")
                buy_qty = promo.conditions.get("buy_quantity", 1)
                get_qty = promo.rewards.get("get_quantity", 1)
                if target_prod:
                    for item in cart.cart_items:
                        if item.product_id == target_prod and item.quantity >= buy_qty:
                            # Simplification: discount the get_qty
                            price = _get_price(item)
                            discount_sets = item.quantity // (buy_qty + get_qty)
                            if discount_sets == 0 and item.quantity > buy_qty:
                                discount_sets = 1
                            discount = discount_sets * get_qty * price
                            subtotal -= discount
                            applied_promotions.append(promo.name)
                            
        if subtotal < 0:
            subtotal = 0.0
        
        total_items = sum(item.quantity for item in cart.cart_items)

        for item in cart.cart_items:
            product = item.product
            price = _get_price(item)
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
            price = _get_price(item)
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
        }
        
    def apply_coupon(self, cart: Cart, code: str) -> Cart:
        coupon = self.db.execute(select(Coupon).where(Coupon.code == code)).scalar_one_or_none()
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
            
        if not coupon.is_valid:
            raise HTTPException(status_code=400, detail="Coupon is invalid, expired, or usage limit reached")
            
        raw_subtotal = sum(item.quantity * float(item.product.price) for item in cart.cart_items)
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
