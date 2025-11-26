from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select


from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.address import Address
from app.core.exceptions import OrderException
from app.models.user import User
from app.utils.order_utils import generate_order_number, generate_trx_ref
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
            tx_ref=generate_trx_ref(),
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

    def get_total_orders(self):
        total_orders = self.db.query(func.count()).scalar() or 0
        return total_orders

    def get_total_revenue(self):
        total_revenue = self.db.query(func.sum(Order.total_amount)).scalar() or 0.0
        return total_revenue

    def get_pending_orders(self):
        pending_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "pending")
            .scalar()
            or 0
        )
        return pending_orders

    def get_paid_orders(self):
        paid_orders = (
            self.db.query(func.count(Order.id)).filter(Order.status == "paid").scalar()
            or 0
        )
        return paid_orders

    def get_shipped_orders_count(self):
        shipped_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "shipped")
            .scalar()
            or 0
        )
        return shipped_orders

    def get_delivered_orders_count(self):
        delivered_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "delivered")
            .scalar()
            or 0
        )
        return delivered_orders

    def get_cancelled_orders_count(self):
        cancelled_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "cancelled")
            .scalar()
            or 0
        )
        return cancelled_orders

    def revenue_last_thirty_days(self):
        thirty_days_ago = datetime.now() - timedelta(days=30)
        revenue_last_30_days = (
            self.db.query(func.sum(Order.total_amount))
            .filter(Order.order_date >= thirty_days_ago)
            .scalar()
            or 0.0
        )
        return revenue_last_30_days

    def total_order_by_user(self, user_id: int):
        total_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.user_id == user_id)
            .scalar()
            or 0
        )
        return total_orders

    def total_spent_by_user(self, user_id: int):
        total_spent = (
            self.db.query(func.sum(Order.total_amount))
            .filter(Order.user_id == user_id)
            .scalar()
            or 0.0
        )
        return total_spent

    def get_all_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """Get paginated list of all orders with optional filters"""
        query = self.db.query(Order).join(User, Order.user_id == User.id)

        # Apply filters
        if status:
            query = query.filter(Order.status == status)
        if user_id:
            query = query.filter(Order.user_id == user_id)

        # Get total count
        total = query.count()

        # Apply pagination and ordering (newest first)
        offset = (page - 1) * page_size
        orders = (
            query.order_by(Order.order_date.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return total, orders

    def update_order_status(self, order_id: int, new_status: str) -> Order:
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        order.status = new_status
        self.db.commit()
        self.db.refresh(order)
        return order

    def mark_order_shipped(
        self, order_id: int, shipped_at: Optional[datetime] = None
    ) -> Order:
        """Mark an order as shipped"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        order.status = "shipped"
        order.shipped_at = shipped_at or datetime.now()
        self.db.commit()
        self.db.refresh(order)
        return order
