from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.payment import Payment
from datetime import datetime


class PaymentCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_payment(
        self,
        order_id: int,
        amount: float,
        transaction_id: str,
        payment_method: str = "stripe",
    ):
        payment = Payment(
            order_id=order_id,
            amount=amount,
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

    def update_payment_status(self, payment: Payment, status: str):
        payment.status = status
        if status == "completed":
            payment.paid_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(payment)
        return payment
