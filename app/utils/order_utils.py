from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.crud.cart_item import CartCrud
import datetime
import uuid

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product


def generate_order_number() -> str:
    return f"ORD-{datetime.date.today().strftime('%Y%m%d,%H%M%S')}-{str(uuid.uuid4())[:10].upper()}"


def generate_trx_ref() -> str:
    return f"TX-{str(uuid.uuid4())}"


def pre_checkout_validate(self, cart: Cart):
    """Check stock for all items in the cart. Raise HTTPException if any out-of-stock."""
    out_of_stock = []
    for item in cart.cart_items:
        product = self.db.get(Product, item.product_id)
        if not product:
            out_of_stock.append((item.product_id, "product not found"))
            continue
        if product.stock_quantity is None or product.stock_quantity < item.quantity:
            out_of_stock.append(
                (product.id, f"only {product.stock_quantity or 0} available")
            )
    if out_of_stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"out_of_stock": out_of_stock},
        )
    return True
