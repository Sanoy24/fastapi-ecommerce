from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.payment import Payment
from app.utils.time import utcnow


class PaymentCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_payment(
        self,
        order_id: int,
        amount: float,
        transaction_id: str,
        currency_code: str,
        payment_method: str = "stripe",
    ):
        payment = Payment(
            order_id=order_id,
            amount=amount,
            currency_code=currency_code,
            transaction_id=transaction_id,
            payment_method=payment_method,
            status="pending",
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def get_payment_by_transaction_id(self, transaction_id: str):
        stmt = select(Payment).where(Payment.transaction_id == transaction_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def update_payment_status(self, payment: Payment, status: str, *, commit: bool = True):
        """Set a payment's status. Pass commit=False when the caller owns the
        transaction (the webhook handler commits the status change together
        with the order update and the event record, or rolls all of it back)."""
        payment.status = status
        if status == "completed":
            payment.paid_at = utcnow()
        if commit:
            self.db.commit()
            self.db.refresh(payment)
        else:
            self.db.flush()
        return payment
