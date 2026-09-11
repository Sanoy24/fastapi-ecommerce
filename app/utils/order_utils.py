from fastapi import HTTPException, status
import datetime
import uuid

from app.models.cart import Cart
from app.models.product import Product


def generate_order_number() -> str:
    """ORD-<date>-<time>-<10 random hex chars>, e.g. ORD-20260911-153045-A1B2C3D4E5.

    Was previously built from datetime.date.today(), a date with no time
    component at all, so '%H%M%S' always rendered as 000000 — every order
    number read like ORD-20260911,000000-... — plus a stray comma from the
    format string joining the two directly. Uniqueness was never actually
    at risk (the random suffix alone makes a collision astronomically
    unlikely), this only ever affected what a human reading the number saw.
    """
    now = datetime.datetime.now()
    return f"ORD-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{str(uuid.uuid4())[:10].upper()}"


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
