import stripe
from fastapi import HTTPException, status
from app.core.config import settings
from app.crud.payment import PaymentCrud
from app.crud.order import OrderCrud
from app.models.order import Order

stripe.api_key = settings.STRIPE_SECRET_KEY


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

        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            self._handle_successful_payment(payment_intent)
        elif event["type"] == "payment_intent.payment_failed":
            payment_intent = event["data"]["object"]
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
                self.db.commit()
