from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product
from app.models.coupon import Coupon
from app.schema.cart_schema import CartItemCreate, CartItemUpdate
from app.schema.coupon_schema import CouponPublic
import datetime
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
        if product.stock_quantity < data.quantity:
            raise ProductException("Product out of stock")

        existing = self.cart_crud.get_cart_item_by_product(cart.id, product.id)

        if existing:
            result = self.cart_crud.update_existing_cart_item(
                cart.id, product.id, data.quantity
            )
            return result

        new_item = self.cart_crud.add_new_cart_item(
            cart_id=cart.id, product_id=product.id, quantity=data.quantity
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
        raw_subtotal = sum(item.quantity * float(item.product.price) for item in cart.cart_items)
        subtotal = raw_subtotal
        
        if cart.coupon_id and cart.coupon:
            if cart.coupon.is_valid and (cart.coupon.min_order_value is None or raw_subtotal >= float(cart.coupon.min_order_value)):
                if cart.coupon.discount_type == "percentage":
                    discount = raw_subtotal * (float(cart.coupon.discount_value) / 100)
                    subtotal -= discount
                elif cart.coupon.discount_type == "fixed":
                    subtotal -= float(cart.coupon.discount_value)
            
            if subtotal < 0:
                subtotal = 0.0
        
        total_items = sum(item.quantity for item in cart.cart_items)

        for item in cart.cart_items:
            product = item.product
            item_sub = product.price * item.quantity

            items.append(
                {
                    "id": item.id,
                    "product_id": product.id,
                    "quantity": item.quantity,
                    "product_name": product.name,
                    "unit_price": product.price,
                    "subtotal": item_sub,
                }
            )

        return {
            "id": cart.id,
            "items": items,
            "total_items": total_items,
            "subtotal": raw_subtotal,
            "coupon_code": cart.coupon.code if cart.coupon else None,
            "discount_amount": raw_subtotal - subtotal,
            "total_amount": subtotal,
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

    def merge_carts(self, user_id: int, session_id: str):
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
                user_cart.id, item.product_id
            )

            if existing:
                existing.quantity += item.quantity
            else:
                item.cart_id = user_cart.id
        self.cart_crud.remove_anon_cart(session_id=session_id)
