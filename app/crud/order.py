from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select


from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_event import OrderEvent
from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.address import Address
from app.models.coupon_usage import CouponUsage
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_transaction import InventoryTransaction
from app.models.shipment import Shipment
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
            if item.variant_id:
                from app.models.product_variant import ProductVariant
                variant = (
                    self.db.execute(
                        select(ProductVariant).where(ProductVariant.id == item.variant_id).with_for_update()
                    ).scalars().first()
                )
                if not variant:
                    raise OrderException(f"Variant not found: {item.variant_id}")
                if variant.stock_quantity < item.quantity:
                    raise OrderException(f"Not enough stock for variant. Available: {variant.stock_quantity}")
            else:
                product = (
                    self.db.execute(
                        select(Product).where(Product.id == item.product_id).with_for_update()
                    )
                    .scalars()
                    .first()
                )
                if not product:
                    raise OrderException(f"Product not found: {item.product_id}")
                if product.available_stock < item.quantity:
                    raise OrderException(
                        f"Not enough stock for {product.name}. "
                        f"Available: {product.available_stock}"
                    )

    def create_order(self, user_id: int, shipping_id: int, billing_id: int):
        shipping_address = self.validate_address(user_id, shipping_id)
        billing_address = self.validate_address(user_id, billing_id)

        # Fetch cart items
        items = self.get_cart_items(user_id)
        self.validate_stock(items)
        
        cart = items[0].cart
        def _get_price(i: CartItem) -> float:
            if i.variant_id and i.variant:
                return float(i.variant.price)
            return float(i.product.price)
        
        raw_subtotal = sum(_get_price(i) * i.quantity for i in items)
        subtotal = float(raw_subtotal)
        discount = 0.0
        
        if cart.coupon and cart.coupon.is_valid:
            # Check if this user already used this coupon
            usage = self.db.query(CouponUsage).filter(
                CouponUsage.coupon_id == cart.coupon_id,
                CouponUsage.user_id == user_id
            ).first()
            
            if usage:
                raise OrderException("You have already used this coupon.")

            if cart.coupon.min_order_value is None or subtotal >= float(cart.coupon.min_order_value):
                if cart.coupon.discount_type == "percentage":
                    discount = subtotal * (float(cart.coupon.discount_value) / 100)
                elif cart.coupon.discount_type == "fixed":
                    discount = float(cart.coupon.discount_value)
                    
        total_amount = max(0.0, subtotal - discount)
        
        def _address_dict(addr):
            return {
                "street": addr.street,
                "city": addr.city,
                "country": addr.country,
                "postal_code": addr.postal_code
            }

        order = Order(
            user_id=user_id,
            shipping_address_id=shipping_id,
            billing_address_id=billing_id,
            shipping_address_snapshot=_address_dict(shipping_address),
            billing_address_snapshot=_address_dict(billing_address),
            coupon_id=cart.coupon_id,
            order_number=generate_order_number(),
            subtotal=subtotal,
            discount_amount=discount,
            total_amount=total_amount,
            status="pending",
            tx_ref=generate_trx_ref(),
        )
        self.db.add(order)
        self.db.flush()  # Get order.id

        # Create order items + reserve stock
        for item in items:
            price = _get_price(item)
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                unit_price=price,
                quantity=item.quantity,
            )
            self.db.add(order_item)

            # Create inventory reservation instead of direct deduction
            reservation = InventoryReservation(
                product_id=item.product_id,
                user_id=user_id,
                quantity=item.quantity,
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
            )
            self.db.add(reservation)

            # Record inventory transaction for reservation
            qty_before = item.variant.stock_quantity if item.variant_id and item.variant else item.product.stock_quantity
            inv_tx = InventoryTransaction(
                product_id=item.product_id,
                order_id=order.id,
                transaction_type="reservation",
                quantity_change=0,  # stock_quantity doesn't change yet, but available_stock effectively does
                quantity_before=qty_before,
                quantity_after=qty_before,
                note=f"Reserved {item.quantity} units for order {order.order_number}",
                created_by=user_id
            )
            self.db.add(inv_tx)

        # Create initial order event
        event = OrderEvent(
            order_id=order.id,
            from_status=None,
            to_status="pending",
            note="Order placed",
            created_by=user_id
        )
        self.db.add(event)

        # Clear cart
        for item in items:
            self.db.delete(item)

        # Record coupon usage if applicable
        if cart.coupon_id and discount > 0:
            usage = CouponUsage(
                coupon_id=cart.coupon_id,
                user_id=user_id,
                order_id=order.id
            )
            self.db.add(usage)
            
        # Update order history
        event = OrderEvent(
            order_id=order.id, status="pending", notes="Order placed successfully"
        )
        self.db.add(event)

        # Outbox Pattern: Insert event into outbox_events in the same transaction
        from app.models.outbox_event import OutboxEvent
        outbox_event = OutboxEvent(
            topic="order.created",
            payload={
                "order_id": order.id,
                "order_number": order.order_number,
                "user_id": order.user_id,
                "total_amount": float(order.total_amount),
            }
        )
        self.db.add(outbox_event)

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

    def update_order_status(self, order_id: int, new_status: str, admin_id: Optional[int] = None) -> Order:
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        valid_transitions = {
            "pending": ["paid", "payment_failed", "cancelled"],
            "paid": ["processing", "refund_pending", "cancelled"],
            "processing": ["shipped", "refund_pending"],
            "shipped": ["delivered", "return_requested"],
            "delivered": ["return_requested"],
            "return_requested": ["return_approved", "cancelled"],
            "refund_pending": ["refunded"],
            "payment_failed": ["cancelled"],
            "cancelled": [],
            "refunded": [],
            "return_approved": []
        }

        allowed_next = valid_transitions.get(order.status, [])
        if new_status not in allowed_next and new_status != order.status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transition from '{order.status}' to '{new_status}'. Allowed: {allowed_next}"
            )

        if order.status != new_status:
            event = OrderEvent(
                order_id=order.id,
                from_status=order.status,
                to_status=new_status,
                note=f"Status updated to {new_status} by admin",
                created_by=admin_id
            )
            self.db.add(event)
            order.status = new_status
            
            if new_status == "delivered":
                order.delivered_at = func.current_timestamp()
            elif new_status == "cancelled":
                order.cancelled_at = func.current_timestamp()
        self.db.commit()
        self.db.refresh(order)
        return order

    def mark_order_shipped(
        self, order_id: int, tracking_number: Optional[str] = None, carrier: Optional[str] = None, shipped_at: Optional[datetime] = None
    ) -> Order:
        """Mark an order as shipped and create a shipment record"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        if order.status not in ["paid", "processing"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot ship order in status {order.status}"
            )

        order.status = "shipped"
        order.shipped_at = shipped_at or datetime.now()
        
        # Create Shipment record
        shipment = Shipment(
            order_id=order.id,
            tracking_number=tracking_number,
            carrier=carrier,
            status="shipped",
            shipped_at=order.shipped_at
        )
        self.db.add(shipment)
        
        event = OrderEvent(
            order_id=order.id,
            from_status="processing",
            to_status="shipped",
            note=f"Order shipped via {carrier} with tracking {tracking_number}" if tracking_number else "Order shipped",
        )
        self.db.add(event)

        self.db.commit()
        self.db.refresh(order)
        return order
