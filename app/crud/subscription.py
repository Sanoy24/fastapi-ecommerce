from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.order import OrderCrud
from app.models.order import Order
from app.models.subscription import Subscription
from app.schema.subscription_schema import SubscriptionCreate
from app.utils.time import utcnow


class SubscriptionCrud:
    def __init__(self, db: Session):
        self.db = db
        self.order_crud = OrderCrud(db)

    def create(self, user_id: int, dto: SubscriptionCreate, next_billing_date: datetime) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            product_id=dto.product_id,
            variant_id=dto.variant_id,
            quantity=dto.quantity,
            interval=dto.interval,
            saved_payment_method_id=dto.saved_payment_method_id,
            shipping_address_id=dto.shipping_address_id,
            billing_address_id=dto.billing_address_id,
            next_billing_date=next_billing_date,
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def get_by_id(self, subscription_id: int) -> Optional[Subscription]:
        return self.db.get(Subscription, subscription_id)

    def list_for_user(self, user_id: int) -> List[Subscription]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_due(self, now: datetime) -> List[Subscription]:
        """Subscriptions the billing task should attempt this run —
        active or past_due (mid-dunning-retry), never paused or already
        cancelled."""
        stmt = select(Subscription).where(
            Subscription.status.in_(["active", "past_due"]),
            Subscription.next_billing_date <= now,
        )
        return list(self.db.scalars(stmt).all())

    def count_for_payment_method(self, saved_payment_method_id: int) -> int:
        """Every subscription that has ever used this payment method, not
        just active ones — the FK is RESTRICT (see Subscription model), so
        even a cancelled subscription's row still references it and would
        make the DELETE fail at the database level regardless of status.
        Mirrors how Order.shipping_address_id/billing_address_id already
        block deleting an address referenced by any order, cancelled or
        not — this app doesn't drop historical FK references just because
        the referencing record is no longer active."""
        stmt = select(Subscription).where(Subscription.saved_payment_method_id == saved_payment_method_id)
        return len(list(self.db.scalars(stmt).all()))

    def pause(self, subscription: Subscription) -> Subscription:
        subscription.status = "paused"
        subscription.paused_at = utcnow()
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def resume(self, subscription: Subscription, next_billing_date: datetime) -> Subscription:
        subscription.status = "active"
        subscription.paused_at = None
        subscription.next_billing_date = next_billing_date
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def skip_next(self, subscription: Subscription, next_billing_date: datetime) -> Subscription:
        """Skipping is a fresh, user-initiated deferral, not another
        payment failure — it clears any in-progress dunning state rather
        than letting a skip count toward the cancellation threshold."""
        subscription.next_billing_date = next_billing_date
        subscription.status = "active"
        subscription.failure_count = 0
        subscription.last_payment_error = None
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def cancel(self, subscription: Subscription) -> Subscription:
        subscription.status = "cancelled"
        subscription.cancelled_at = utcnow()
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def create_renewal_order(self, subscription: Subscription) -> Order:
        return self.order_crud.create_renewal_order(subscription)

    def cancel_renewal_order(self, order: Order) -> None:
        self.order_crud.cancel_renewal_order(order)

    def record_renewal_success(self, subscription: Subscription) -> None:
        now = utcnow()
        subscription.status = "active"
        subscription.failure_count = 0
        subscription.last_payment_error = None
        subscription.next_billing_date = self._next_billing_date_after_success(subscription, now)
        self.db.commit()

    def record_renewal_failure(self, subscription: Subscription, error_message: str) -> bool:
        """Increments the failure count and either reschedules a retry or
        cancels the subscription outright. Returns True if this failure
        cancelled the subscription."""
        from app.utils.subscription_billing import MAX_RENEWAL_FAILURES, compute_retry_date

        now = utcnow()
        subscription.failure_count += 1
        subscription.last_payment_error = error_message[:500]

        if subscription.failure_count > MAX_RENEWAL_FAILURES:
            subscription.status = "cancelled"
            subscription.cancelled_at = now
            self.db.commit()
            return True

        subscription.status = "past_due"
        subscription.next_billing_date = compute_retry_date(subscription.failure_count, from_dt=now)
        self.db.commit()
        return False

    @staticmethod
    def _next_billing_date_after_success(subscription: Subscription, now: datetime) -> datetime:
        from app.utils.subscription_billing import compute_next_billing_date

        return compute_next_billing_date(subscription.interval, from_dt=now)
