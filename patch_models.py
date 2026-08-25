import os
import glob

# Models mapping
models_imports = """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.brand import Brand
    from app.models.cart import Cart
    from app.models.cart_item import CartItem
    from app.models.category import Category
    from app.models.coupon import Coupon
    from app.models.inventory_reservation import InventoryReservation
    from app.models.order import Order
    from app.models.order_event import OrderEvent
    from app.models.order_item import OrderItem
    from app.models.payment import Payment
    from app.models.payment_event import PaymentEvent
    from app.models.price_history import PriceHistory
    from app.models.product import Product
    from app.models.product_image import ProductImage
    from app.models.product_relation import ProductRelation
    from app.models.product_variant import ProductVariant
    from app.models.return_request import ReturnRequest
    from app.models.review import Review
    from app.models.tax_rate import TaxRate
    from app.models.user import User
    from app.models.wishlist import Wishlist
    from app.models.outbox_event import OutboxEvent
"""

for file_path in glob.glob("app/models/*.py"):
    if os.path.basename(file_path) == "__init__.py":
        continue
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "if TYPE_CHECKING:" not in content:
        # Find the end of imports (a crude way: just insert after the first class definition, or before it)
        # Better: insert after the last 'import' line
        lines = content.split('\n')
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_idx = i
                
        new_lines = lines[:last_import_idx+1] + [models_imports] + lines[last_import_idx+1:]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('\n'.join(new_lines))
        print(f"Patched {file_path}")
