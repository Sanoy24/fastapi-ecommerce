from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select


from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_event import OrderEvent
from app.models.product import Product
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.coupon_usage import CouponUsage
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_transaction import InventoryTransaction
from app.models.shipment import Shipment
from app.core.exceptions import OrderException
from app.models.user import User
from app.utils.order_utils import generate_order_number, generate_trx_ref
from app.crud.address import AddressCrud
from app.schema.order_schema import GuestAddressInput
from app.services.pricing import calculate_coupon_discount, calculate_promotion_discount, get_unit_price


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

    def get_guest_cart_items(self, session_id: str):
        """The anonymous-cart equivalent of get_cart_items — same cart the
        guest has been adding to via POST /cart/items with no account."""
        stmt = (
            select(CartItem)
            .join(CartItem.cart)
            .where(Cart.session_id == session_id, Cart.user_id.is_(None))
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
                if variant.available_stock < item.quantity:
                    raise OrderException(f"Not enough stock for variant. Available: {variant.available_stock}")
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

    def create_order(self, user_id: int, shipping_id: int, billing_id: int, shipping_method_id: int | None = None):
        shipping_address = self.validate_address(user_id, shipping_id)
        billing_address = self.validate_address(user_id, billing_id)

        items = self.get_cart_items(user_id)
        self.validate_stock(items)
        cart = items[0].cart

        return self._build_and_persist_order(
            user_id=user_id,
            guest_email=None,
            shipping_address=shipping_address,
            billing_address=billing_address,
            shipping_address_id=shipping_id,
            billing_address_id=billing_id,
            items=items,
            cart=cart,
            shipping_method_id=shipping_method_id,
        )

    def create_guest_order(
        self,
        session_id: str,
        guest_email: str,
        shipping_address: GuestAddressInput,
        billing_address: GuestAddressInput,
        shipping_method_id: int | None = None,
    ):
        """Checkout for an anonymous cart — no account, no saved Address rows.

        Coupons are not supported here: CouponUsage.user_id is NOT NULL, so
        there is no row to record a guest's usage against, and silently
        dropping the discount instead would just overcharge a guest who
        thinks it's applied. Promotions (which aren't user-scoped) still
        apply normally.
        """
        items = self.get_guest_cart_items(session_id)
        self.validate_stock(items)
        cart = items[0].cart

        if cart.coupon_id:
            raise OrderException("Please sign in to check out with a coupon code.")

        return self._build_and_persist_order(
            user_id=None,
            guest_email=guest_email,
            shipping_address=shipping_address,
            billing_address=billing_address,
            shipping_address_id=None,
            billing_address_id=None,
            items=items,
            cart=cart,
            shipping_method_id=shipping_method_id,
        )

    def _build_and_persist_order(
        self,
        *,
        user_id: int | None,
        guest_email: str | None,
        shipping_address,
        billing_address,
        shipping_address_id: int | None,
        billing_address_id: int | None,
        items: list[CartItem],
        cart: Cart,
        shipping_method_id: int | None,
    ) -> Order:
        """Shared body of create_order / create_guest_order.

        shipping_address/billing_address are duck-typed: either a real
        Address row or a GuestAddressInput — both expose the same
        street/city/state/postal_code/country attributes that
        _address_snapshot, _calculate_tax_amount and
        _calculate_shipping_amount actually read.
        """
        raw_subtotal = float(sum(get_unit_price(i) * i.quantity for i in items))
        discount = self._calculate_discount(items, raw_subtotal, cart, user_id)

        region = shipping_address.state or shipping_address.country
        tax_amount = self._calculate_tax_amount(items, region)
        shipping_amount = self._calculate_shipping_amount(shipping_method_id, shipping_address)

        total_amount = max(0.0, raw_subtotal - discount + tax_amount + shipping_amount)

        order = Order(
            user_id=user_id,
            guest_email=guest_email,
            shipping_address_id=shipping_address_id,
            billing_address_id=billing_address_id,
            shipping_address_snapshot=self._address_snapshot(shipping_address),
            billing_address_snapshot=self._address_snapshot(billing_address),
            coupon_id=cart.coupon_id,
            order_number=generate_order_number(),
            subtotal=raw_subtotal,
            discount_amount=discount,
            tax_amount=tax_amount,
            shipping_amount=shipping_amount,
            total_amount=total_amount,
            status="pending",
            tx_ref=generate_trx_ref(),
        )
        self.db.add(order)
        self.db.flush()  # Get order.id

        self._create_order_items_and_reserve_stock(order, items, user_id)

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

        # Record coupon usage if applicable (never true for a guest order —
        # create_guest_order rejects a coupon-bearing cart before this point)
        if cart.coupon_id and discount > 0:
            usage = CouponUsage(
                coupon_id=cart.coupon_id,
                user_id=user_id,
                order_id=order.id
            )
            self.db.add(usage)

        # Outbox Pattern: Insert event into outbox_events in the same transaction
        from app.models.outbox_event import OutboxEvent
        outbox_event = OutboxEvent(
            topic="order.created",
            payload={
                "order_id": order.id,
                "order_number": order.order_number,
                "user_id": order.user_id,
                "guest_email": order.guest_email,
                "total_amount": float(order.total_amount),
            }
        )
        self.db.add(outbox_event)

        self.db.commit()
        self.db.refresh(order)
        return order

    @staticmethod
    def _address_snapshot(addr) -> dict:
        return {
            "street": addr.street,
            "city": addr.city,
            "country": addr.country,
            "postal_code": addr.postal_code,
            "state": addr.state,
        }

    def _calculate_discount(self, items: list[CartItem], raw_subtotal: float, cart, user_id: int | None) -> float:
        """Coupon + promotion discount for a checkout, mirroring what the cart displayed."""
        discount = 0.0

        if cart.coupon and cart.coupon.is_valid:
            # Check if this user already used this coupon
            usage = self.db.query(CouponUsage).filter(
                CouponUsage.coupon_id == cart.coupon_id,
                CouponUsage.user_id == user_id
            ).first()

            if usage:
                raise OrderException("You have already used this coupon.")

            discount += calculate_coupon_discount(raw_subtotal, cart.coupon)

        # Promotions applied at checkout must match what was shown in the cart —
        # see CartService.get_cart_details, which uses the same helper.
        promo_discount, _applied_promotions = calculate_promotion_discount(self.db, list(items))
        discount += promo_discount
        return discount

    def _calculate_tax_amount(self, items: list[CartItem], region: str | None) -> float:
        from app.models.tax_rate import TaxRate

        tax_rates = self.db.scalars(select(TaxRate).where(TaxRate.is_active)).all()
        tax_amount = 0.0

        for item in items:
            product = item.product
            price = get_unit_price(item)

            item_tax = 0.0
            for tr in tax_rates:
                if tr.applies_to == "all":
                    item_tax += price * float(tr.rate)
                elif tr.applies_to == "category" and tr.category_id == product.category_id:
                    item_tax += price * float(tr.rate)
                elif tr.applies_to == "region" and (region and tr.region and tr.region.lower() == region.lower()):
                    item_tax += price * float(tr.rate)

            tax_amount += item_tax * item.quantity

        return round(tax_amount, 2)

    def _calculate_shipping_amount(self, shipping_method_id: int | None, shipping_address) -> float:
        from app.models.shipping import ShippingMethod, ShippingZone, ShippingRate

        if not shipping_method_id:
            return 0.0

        method = self.db.execute(
            select(ShippingMethod).where(ShippingMethod.id == shipping_method_id, ShippingMethod.is_active)
        ).scalar_one_or_none()

        if not method:
            raise OrderException("Invalid or inactive shipping method")

        shipping_amount = float(method.base_rate)

        # Check for zone-specific rates
        # Simplification: we try to match zone by country
        country = shipping_address.country
        if country:
            zones = self.db.scalars(select(ShippingZone)).all()
            matched_zone = None
            for z in zones:
                if z.countries and country in z.countries:
                    matched_zone = z
                    break

            if matched_zone:
                rate = self.db.execute(
                    select(ShippingRate).where(
                        ShippingRate.zone_id == matched_zone.id,
                        ShippingRate.method_id == method.id
                    )
                ).scalar_one_or_none()

                if rate and rate.base_rate_override is not None:
                    shipping_amount = float(rate.base_rate_override)

        return shipping_amount

    def _create_order_items_and_reserve_stock(self, order: Order, items: list[CartItem], user_id: int | None) -> None:
        """Create OrderItem rows and reserve stock instead of deducting it directly.
        Actual deduction happens on successful payment — see
        PaymentService._handle_successful_payment.
        """
        for item in items:
            price = get_unit_price(item)
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                unit_price=price,
                quantity=item.quantity,
            )
            self.db.add(order_item)

            # variant_id is set for variant items so the reservation is
            # scoped to the variant's own stock pool, not the parent product's
            # — see ProductVariant.available_stock / Product.available_stock.
            # order_id is what release logic (PaymentService,
            # OrderService.cancel_order) must filter on — never user_id,
            # which is None for every guest order and would match every
            # other in-flight guest reservation, not just this order's.
            reservation = InventoryReservation(
                product_id=item.product_id,
                variant_id=item.variant_id,
                user_id=user_id,
                order_id=order.id,
                quantity=item.quantity,
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
            )
            self.db.add(reservation)

            qty_before = item.variant.stock_quantity if item.variant_id and item.variant else item.product.stock_quantity
            inv_tx = InventoryTransaction(
                product_id=item.product_id,
                variant_id=item.variant_id,
                order_id=order.id,
                transaction_type="reservation",
                quantity_change=0,  # stock_quantity doesn't change yet, but available_stock effectively does
                quantity_before=qty_before,
                quantity_after=qty_before,
                note=f"Reserved {item.quantity} units for order {order.order_number}",
                created_by=user_id
            )
            self.db.add(inv_tx)

    def get_orders(self, user_id: int):
        stmt = select(Order).where(Order.user_id == user_id)
        return self.db.scalars(stmt).all()

    def get_order_by_id(self, user_id: int, order_id: int):
        order = self.db.get(Order, order_id)
        if not order or order.user_id != user_id:
            raise OrderException("Order not found")
        return order

    def get_guest_order_by_number_and_email(self, order_number: str, email: str) -> Order | None:
        """Look up a still-unclaimed guest order.

        Only matches orders with user_id IS NULL — once claimed (see
        OrderService.claim_guest_order), the order is no longer reachable
        this way; logging into the account it was claimed into is the only
        path in. Email is compared case-insensitively since a guest may not
        type it identically to how it was originally entered.
        """
        stmt = select(Order).where(
            Order.order_number == order_number,
            Order.user_id.is_(None),
            Order.guest_email.isnot(None),
            func.lower(Order.guest_email) == email.lower(),
        )
        return self.db.scalars(stmt).first()

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
        # outerjoin, not join: an inner join here would silently exclude
        # every guest order (user_id IS NULL) from the admin order list —
        # they'd never appear for fulfillment, shipping, or refunds.
        query = self.db.query(Order).outerjoin(User, Order.user_id == User.id)

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
            "paid": ["processing", "refund_pending", "refunded", "cancelled"],
            "processing": ["packed", "shipped", "refund_pending", "refunded"],
            "packed": ["shipped", "refund_pending"],
            "shipped": ["delivered", "return_requested", "refunded"],
            "delivered": ["return_requested", "refunded"],
            # "delivered": a rejected return reverts the order to its prior
            # delivered state (see admin.py resolve_return) — this was
            # missing, so a rejection's attempt to revert silently failed
            # (caught and swallowed as an "already in that state" no-op)
            # and the order stayed stuck at "return_requested" forever.
            "return_requested": ["return_approved", "delivered", "cancelled"],
            "refund_pending": ["refunded"],
            "payment_failed": ["cancelled"],
            "cancelled": [],
            "refunded": [],
            "return_approved": ["refunded"]
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
                # The Shipment row has its own status/delivered_at — a
                # tracking view reads those, not Order's copy — and
                # previously never got updated here at all, so it stayed
                # stuck at "shipped" forever even after real delivery.
                for shipment in order.shipments:
                    if shipment.status == "shipped":
                        shipment.status = "delivered"
                        shipment.delivered_at = order.delivered_at
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
        order.tracking_number = tracking_number
        order.shipping_carrier = carrier

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
