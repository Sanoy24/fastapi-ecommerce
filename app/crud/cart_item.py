from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProductException
from app.crud.product import ProductCrud
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.schema.cart_schema import CartItemCreate, CartItemUpdate


class CartCrud:
    def __init__(self, db: Session):
        self.db = db
        self.prod_crud = ProductCrud(db)

    def get_or_create_cart(self, user_id: Optional[int], session_id: Optional[str]):
        if user_id:
            stmt = select(Cart).where(Cart.user_id == user_id)
            cart = self.db.scalar(stmt)
            if cart:
                return cart
            cart = Cart(user_id=user_id)
            self.db.add(cart)
            self.db.commit()
            self.db.refresh(cart)
            return cart
        else:
            stmt = select(Cart).where(Cart.session_id == session_id)
            cart = self.db.scalar(stmt)
            if cart:
                return cart
            cart = Cart(session_id=session_id)
            return cart

    def add_item(self, cart: Cart, data: CartItemCreate):
        product = self.prod_crud.get_product_by_id(data.product_id)
        if not product:
            raise ProductException("product not found")

        stmt = select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.product_id == data.product_id
        )

        existing = self.db.scalar(stmt)
        if existing:
            existing.quantity += data.quantity
            self.db.commit()
            self.db.refresh(existing)
            return existing

        new_item = CartItem(
            cart_id=cart.id, product_id=data.product_id, quantity=data.quantity
        )
        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)
        return new_item

    def update_item(self, cart: Cart, item_id: int, data: CartItemUpdate):
        stmt = select(CartItem).where(
            CartItem.id == item_id, CartItem.cart_id == cart.id
        )

        item = self.db.scalar(stmt)
        if not item:
            raise HTTPException(
                status=status.HTTP_404_NOT_FOUND, detail="Item not found"
            )
        item.quantity = data.quantity
        self.db.commit()
        self.db.refresh(item)
        return item

    def remove_item(self, cart: Cart, item_id: int):
        stmt = select(CartItem).where(
            CartItem.id == item_id, CartItem.cart_id == cart.id
        )

        item = self.db.scalar(stmt)

        if not item:
            raise HTTPException(
                status=status.HTTP_404_NOT_FOUND, detail="Item not found"
            )
        self.db.delete(item)
        self.db.commit()
        return True

    def get_cart_details(self, cart: Cart):
        items = []
        subtotal = 0
        total_items = 0

        for item in cart.cart_items:
            product = item.product
            item_sub = product.price * product.quantity

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

            subtotal += item_sub
            total_items += item.quantity

            return {
                "id": cart.id,
                "items": items,
                "subtotal": subtotal,
                "total_items": total_items,
            }

    def merge_carts(self, db: Session, user_id: int, session_id: str):
        stmt_user_cart = select(Cart).where(Cart.user_id == user_id)
        stmt_anon_cart = select(Cart).where(Cart.session_id == session_id)

        user_cart = self.db.scalar(stmt_user_cart)
        anon_cart = self.db.scalar(stmt_anon_cart)

        if not anon_cart:
            return

        if not user_cart:
            anon_cart.user_id = user_id
            anon_cart.session_id = None
            self.db.commit()
            return

        for item in anon_cart.cart_items:
            stmt = select(CartItem).where(
                CartItem.cart_id == user_cart.id, CartItem.product_id == item.product_id
            )

            existing = self.db.scalar(stmt)

            if existing:
                existing.quantity += item.quantity
            else:
                item.cart_id = user_cart.id

        self.db.delete(anon_cart)
        self.db.commit()
