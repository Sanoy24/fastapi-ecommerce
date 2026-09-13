from typing import Optional

import stripe
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.crud.payment import PaymentCrud
from app.crud.order import OrderCrud
from app.crud.saved_payment_method_crud import SavedPaymentMethodCrud
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_transaction import InventoryTransaction

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.max_network_retries = 3


class PaymentService:
    def __init__(self, db):
        self.db = db
        self.payment_crud = PaymentCrud(db)
        self.order_crud = OrderCrud(db)
        self.saved_payment_method_crud = SavedPaymentMethodCrud(db)

    def create_payment_intent(
        self, user_id: int, order_id: int, saved_payment_method_id: Optional[int] = None
    ):
        # get order
        order = self.order_crud.get_order_by_id(user_id, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        stripe_customer_id = None
        stripe_payment_method_id = None
        if saved_payment_method_id is not None:
            method = self.saved_payment_method_crud.get_by_id(saved_payment_method_id)
            if not method or method.user_id != user_id:
                raise HTTPException(status_code=404, detail="Saved payment method not found")
            stripe_customer_id = self.saved_payment_method_crud.get_user_stripe_customer_id(user_id)
            stripe_payment_method_id = method.stripe_payment_method_id

        return self._create_payment_intent_for_order(
            order, stripe_customer_id=stripe_customer_id, stripe_payment_method_id=stripe_payment_method_id
        )

    def create_guest_payment_intent(self, order_number: str, email: str):
        """The guest-checkout equivalent of create_payment_intent.

        A guest has no account to authenticate with, so order_number + email
        stands in for it — the same proof-of-ownership pair used by the
        order lookup and claim-link endpoints.
        """
        order = self.order_crud.get_guest_order_by_number_and_email(order_number, email)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        return self._create_payment_intent_for_order(order)

    def _create_payment_intent_for_order(
        self,
        order: Order,
        stripe_customer_id: Optional[str] = None,
        stripe_payment_method_id: Optional[str] = None,
    ):
        if order.payment_status == "success":
            raise HTTPException(status_code=400, detail="Order already paid")

        amount = int(order.total_amount * 100)  # Amount in cents
        metadata = {
            "order_id": str(order.id),
            "user_id": str(order.user_id) if order.user_id is not None else "guest",
        }

        # Pre-attaching a saved card lets the frontend skip re-collecting
        # card details and go straight to confirming with Stripe.js — it
        # does not confirm the PaymentIntent itself, so the existing
        # client-side confirm step and webhook handling below are
        # unchanged either way.
        try:
            if stripe_payment_method_id:
                # A SavedPaymentMethod row only ever exists after its
                # user's stripe_customer_id was set (see
                # SavedPaymentMethodService.get_or_create_stripe_customer_id),
                # so create_payment_intent above always resolves both
                # together or neither.
                assert stripe_customer_id is not None
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency="usd",
                    metadata=metadata,
                    customer=stripe_customer_id,
                    payment_method=stripe_payment_method_id,
                )
            else:
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency="usd",
                    metadata=metadata,
                    automatic_payment_methods={"enabled": True},
                )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Create local Payment record
        self.payment_crud.create_payment(
            order_id=order.id,
            amount=order.total_amount,
            transaction_id=intent.id,
            payment_method="stripe",
        )

        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": order.total_amount,
            "currency": "usd",
        }

    def handle_webhook(self, payload, sig_header):
        event = None
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

        provider_event_id = event["id"]

        # Deduplication using database unique constraint
        try:
            payment_event = PaymentEvent(
                event_type=event["type"],
                provider_event_id=provider_event_id,
                payload=event,
                is_duplicate=False
            )
            self.db.add(payment_event)
            self.db.commit()
            self.db.refresh(payment_event)
        except IntegrityError:
            self.db.rollback()
            return {"status": "success", "detail": "Duplicate event ignored"}

        # Attempt to link event to payment if transaction_id is present
        payment_intent = event["data"]["object"]
        transaction_id = payment_intent.get("id")
        payment = None
        if transaction_id:
            payment = self.payment_crud.get_payment_by_transaction_id(transaction_id)
            if payment:
                payment_event.payment_id = payment.id
                self.db.commit()

        if event["type"] == "payment_intent.succeeded":
            self._handle_successful_payment(payment_intent)
        elif event["type"] == "payment_intent.payment_failed":
            self._handle_failed_payment(payment_intent)

        return {"status": "success"}

    def _handle_successful_payment(self, payment_intent):
        transaction_id = payment_intent["id"]
        payment = self.payment_crud.get_payment_by_transaction_id(transaction_id)
        if payment:
            self.payment_crud.update_payment_status(payment, "completed")

            # Update Order Status
            order = self.db.get(Order, payment.order_id)
            if order:
                order.payment_status = "success"
                order.status = "paid"

                # Deduct stock and clear reservations. A variant item deducts
                # from the variant's own stock_quantity, not the parent
                # product's — they're separate pools (see
                # ProductVariant.available_stock).
                for item in order.order_items:
                    if item.variant_id and item.variant:
                        variant = item.variant
                        old_qty = variant.stock_quantity
                        variant.stock_quantity -= item.quantity

                        inv_tx = InventoryTransaction(
                            product_id=item.product_id,
                            variant_id=variant.id,
                            order_id=order.id,
                            transaction_type="deduction",
                            quantity_change=-item.quantity,
                            quantity_before=old_qty,
                            quantity_after=variant.stock_quantity,
                            note=f"Stock deducted after successful payment for order {order.order_number}"
                        )
                        self.db.add(inv_tx)
                    elif item.product:
                        product = item.product
                        old_qty = product.stock_quantity
                        product.stock_quantity -= item.quantity

                        inv_tx = InventoryTransaction(
                            product_id=product.id,
                            order_id=order.id,
                            transaction_type="deduction",
                            quantity_change=-item.quantity,
                            quantity_before=old_qty,
                            quantity_after=product.stock_quantity,
                            note=f"Stock deducted after successful payment for order {order.order_number}"
                        )
                        self.db.add(inv_tx)

                # order_id, not user_id: see the comment in
                # OrderService.cancel_order for why filtering by user_id
                # here would clear reservations belonging to a different
                # order (or, for a guest, every other guest order in flight).
                reservations = self.db.query(InventoryReservation).filter(
                    InventoryReservation.order_id == order.id
                ).all()
                for res in reservations:
                    self.db.delete(res)

                self.db.commit()

    def _handle_failed_payment(self, payment_intent):
        transaction_id = payment_intent["id"]
        payment = self.payment_crud.get_payment_by_transaction_id(transaction_id)
        if payment:
            self.payment_crud.update_payment_status(payment, "failed")

            # Update Order Status
            order = self.db.get(Order, payment.order_id)
            if order:
                order.payment_status = "failed"

                # Clear this order's reservations — order_id, not user_id
                # (see OrderService.cancel_order for why).
                reservations = self.db.query(InventoryReservation).filter(
                    InventoryReservation.order_id == order.id
                ).all()
                for res in reservations:
                    self.db.delete(res)

                self.db.commit()

    def refund_payment(self, order_id: int, admin_id: int, amount: float, reason: str):
        """Admin-only: refund all or part of an order's payment via Stripe.

        Customers cannot call this directly — they file a return via
        POST /order/{order_id}/return, which an admin approves and then
        refunds through POST /admin/orders/{order_id}/refund.
        """
        order = self.db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.payment_status != "success":
            raise HTTPException(status_code=400, detail="Cannot refund unpaid order")

        if order.status not in ["paid", "processing", "shipped", "delivered", "return_approved"]:
            raise HTTPException(status_code=400, detail=f"Cannot refund order in status {order.status}")

        payment = self.db.query(Payment).filter(Payment.order_id == order.id, Payment.status == "completed").first()
        if not payment or not payment.transaction_id:
            raise HTTPException(status_code=400, detail="No completed payment transaction found")

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be positive")

        already_refunded = float(payment.refund_amount or 0)
        remaining = float(order.total_amount) - already_refunded
        if amount > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Refund amount exceeds remaining refundable balance of {remaining:.2f}",
            )

        try:
            refund = stripe.Refund.create(
                payment_intent=payment.transaction_id,
                amount=int(amount * 100),
                reason="requested_by_customer" if reason == "duplicate" else "requested_by_customer"  # stripe reasons are restricted
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        payment.refund_amount = already_refunded + amount
        payment.refunded_at = func.current_timestamp()

        # update order status
        self.order_crud.update_order_status(order.id, "refunded", admin_id=admin_id)
        self.db.commit()
        return refund

