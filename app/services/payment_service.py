import stripe
from fastapi import HTTPException, status
from app.core.config import settings
from app.crud.payment import PaymentCrud
from app.crud.order import OrderCrud
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.inventory_reservation import InventoryReservation
from sqlalchemy.exc import IntegrityError

stripe.api_key = settings.STRIPE_SECRET_KEY
from sqlalchemy import func


class PaymentService:
    def __init__(self, db):
        self.db = db
        self.payment_crud = PaymentCrud(db)
        self.order_crud = OrderCrud(db)

    def create_payment_intent(self, user_id: int, order_id: int):
        # get order
        order = self.order_crud.get_order_by_id(user_id, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.payment_status == "success":
            raise HTTPException(status_code=400, detail="Order already paid")

        # Create Stripe PaymentIntent
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),  # Amount in cents
                currency="usd",
                metadata={"order_id": order.id, "user_id": user_id},
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
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
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
                
                # Deduct stock and clear reservations
                for item in order.order_items:
                    product = item.product
                    if product:
                        product.stock_quantity -= item.quantity
                        
                reservations = self.db.query(InventoryReservation).filter(
                    InventoryReservation.user_id == order.user_id
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
                
                # Clear reservations
                reservations = self.db.query(InventoryReservation).filter(
                    InventoryReservation.user_id == order.user_id
                ).all()
                for res in reservations:
                    self.db.delete(res)

                self.db.commit()

    def refund_payment(self, order_id: int, user_id: int, amount: float, reason: str, is_admin: bool = False):
        order = self.order_crud.get_order_by_id(user_id, order_id) if not is_admin else self.db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.payment_status != "success":
            raise HTTPException(status_code=400, detail="Cannot refund unpaid order")

        if order.status not in ["paid", "processing", "shipped", "delivered", "return_approved"]:
            raise HTTPException(status_code=400, detail=f"Cannot refund order in status {order.status}")

        payment = self.db.query(Payment).filter(Payment.order_id == order.id, Payment.status == "completed").first()
        if not payment or not payment.transaction_id:
            raise HTTPException(status_code=400, detail="No completed payment transaction found")

        try:
            refund = stripe.Refund.create(
                payment_intent=payment.transaction_id,
                amount=int(amount * 100),
                reason="requested_by_customer" if reason == "duplicate" else "requested_by_customer"  # stripe reasons are restricted
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        payment.refund_amount = amount
        payment.refunded_at = func.current_timestamp()
        
        # update order status
        self.order_crud.update_order_status(order.id, "refunded", admin_id=user_id if is_admin else None)
        self.db.commit()
        return refund

