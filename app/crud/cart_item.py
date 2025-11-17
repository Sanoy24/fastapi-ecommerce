from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProductException
from app.crud.product import ProductCrud
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.schema.cart_schema import CartItemCreate, CartItemUpdate
from app.core.logger import logger


class CartCrud:
    def __init__(self, db: Session):
        self.db = db
        self.prod_crud = ProductCrud(db)

    def get_cart_by_user_id(self, user_id: int) -> Cart | None:
        stmt = (
            select(Cart)
            .where(Cart.user_id == user_id)
            .options(selectinload(Cart.cart_items).selectinload(CartItem.product))
        )
        cart = self.db.scalar(stmt)
        if not cart:
            return None
        return cart

    def get_cart_by_session_id(self, session_id: int) -> Cart | None:
        stmt = (
            select(Cart)
            .where(Cart.session_id == session_id)
            .options(selectinload(Cart.cart_items).selectinload(CartItem.product))
        )
        cart = self.db.scalar(stmt)
        if not cart:
            return None
        return cart

    def create_cart_by_user_id(self, user_id: int) -> Cart:
        cart = Cart(user_id=user_id)
        self.db.add(cart)
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def create_cart_by_session_id(self, session_id: int) -> Cart:
        cart = Cart(session_id=session_id)
        self.db.add(cart)
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def get_cart_item_by_product(self, cart_id: int, product_id: int):
        stmt = select(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.product_id == product_id
        )

        cart_item = self.db.scalar(stmt)
        if not cart_item:
            return None
        return cart_item

    def update_existing_cart_item(
        self, cart_id: int, product_id: int, quantity: int
    ) -> CartItem:
        stmt = (
            update(CartItem)
            .where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
            .values(quantity=CartItem.quantity + quantity)
            .returning(CartItem)
        )

        updated = self.db.execute(stmt).scalar_one_or_none()
        self.db.commit()
        return updated

    def add_new_cart_item(
        self, cart_id: int, product_id: int, quantity: int
    ) -> CartItem:
        new_item = CartItem(cart_id=cart_id, product_id=product_id, quantity=quantity)
        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)
        return new_item

    def get_cart_item_by_cart_id(self, cart_id: int, item_id: int) -> CartItem:
        stmt = select(CartItem).where(
            CartItem.id == item_id, CartItem.cart_id == cart_id
        )
        result = self.db.scalar(stmt)
        if not result:
            return None
        return result

    def update_item(self, cart_id: int, item_id: int, data: CartItemUpdate) -> CartItem:
        stmt = (
            update(CartItem)
            .where(CartItem.id == item_id, CartItem.cart_id == cart_id)
            .values(quantity=data.quantity)
            .returning(CartItem)
        )
        updated = self.db.execute(stmt).scalar_one_or_none()
        self.db.commit()
        return updated

    def remove_item(self, cart_id: int, item_id: int):
        stmt = delete(CartItem).where(
            CartItem.id == item_id, CartItem.cart_id == cart_id
        )
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        return True

    def remove_anon_cart(self, session_id: str):
        stmt = delete(Cart).where(Cart.session_id == session_id)
        result = self.db.execute(stmt)
        if result.rowcount == 0:
            return False
        self.db.commit()
        # return True

    def update_anon_cart_to_user_cart(self, user_id: int, session_id: str):
        logger.info(f"update anon cart to user cart: {user_id}")
        stmt = (
            update(Cart)
            .where(Cart.session_id == session_id)
            .values(user_id=user_id, session_id=None)
            .returning(Cart.id)
        )
        self.db.execute(stmt).scalar_one_or_none()
        self.db.commit()
