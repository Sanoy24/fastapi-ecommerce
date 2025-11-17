from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.address import Address
from app.core.exceptions import OrderException
from app.utils.order_utils import generate_order_number
from app.crud.address import AddressCrud


class OrderCrud:
    def __init__(self, db: Session):
        self.db = db
        self.address_crud = AddressCrud(db=db)

    def validate_address(self, user_id: int, address_id: int):
        address = self.address_crud.get_single_address(address_id)
        if not address or address.user_id != user_id:
            raise OrderException("Invalid address")
        return address

    def get_cart_items(self, user_id: int):
        stmt = (
            select(CartItem)
            .join(CartItem.cart)
            .where(CartItem.cart.has(user_id=user_id))
        )
        items = self.db.scalars(stmt).all()
        if not items:
            raise OrderException("Your cart is empty.")
        return items

    def validate_stock(self, items: list[CartItem]):
        for item in items:
            if item.product.stock_quantity < item.quantity:
                raise OrderException(
                    f"Not enough stock for {item.product.name}. "
                    f"Available: {item.product.stock_quantity}"
                )

    def create_order(self, user_id: int, shipping_id: int, billing_id: int):
        # Validate addresses
        self.validate_address(user_id, shipping_id)
        self.validate_address(user_id, billing_id)

        # Fetch cart items
        items = self.get_cart_items(user_id)
        self.validate_stock(items)

        # Compute total
        total_amount = sum(i.product.price * i.quantity for i in items)

        order = Order(
            user_id=user_id,
            shipping_address_id=shipping_id,
            billing_address_id=billing_id,
            order_number=generate_order_number(),
            total_amount=total_amount,
            status="pending",
        )
        self.db.add(order)
        self.db.flush()  # Get order.id

        # Create order items + reduce stock
        for item in items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                unit_price=item.product.price,
                quantity=item.quantity,
            )
            self.db.add(order_item)

            # Reduce stock
            item.product.stock_quantity -= item.quantity

        # Clear cart
        for item in items:
            self.db.delete(item)

        self.db.commit()
        self.db.refresh(order)
        return order

    def get_orders(self, user_id: int):
        stmt = select(Order).where(Order.user_id == user_id)
        return self.db.scalars(stmt).all()

    def get_order_by_id(self, user_id: int, order_id: int):
        order = self.db.get(Order, order_id)
        if not order or order.user_id != user_id:
            raise OrderException("Order not found")
        return order
