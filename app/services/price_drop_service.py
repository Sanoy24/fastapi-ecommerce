from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.price_drop_crud import PriceDropCrud
from app.models.outbox_event import OutboxEvent
from app.models.price_drop_subscription import PriceDropSubscription
from app.models.product import Product
from app.schema.price_drop_schema import PriceDropSubscriptionResponse
from app.utils.time import utcnow


def notify_price_drop_subscribers(
    db: Session,
    *,
    product_id: int,
    old_effective_price: float,
    new_effective_price: float,
) -> None:
    """Call this wherever Product.price or Product.sale_price changes such
    that effective_price could move — see app/crud/product.py
    (update_product) for the current call site.

    Written as an explicit call at the site rather than a SQLAlchemy ORM
    event, matching how the rest of this codebase surfaces side effects
    (e.g. InventoryTransaction rows, outbox events, back-in-stock
    notifications) — see notify_back_in_stock_subscribers for the same
    reasoning.

    Writes an outbox event per matching subscription rather than sending
    email directly, for the same "runs inside the same transaction as the
    price update" reason as notify_back_in_stock_subscribers: if that
    transaction rolls back, the notification should never have been queued.
    See app/workers/arq_worker.py process_outbox_events_task for where
    "product.price_drop" events actually get turned into emails.

    A subscription with target_price set only fires once the price falls to
    that amount or below; one with target_price=None fires on any decrease
    from the price captured when the customer subscribed
    (subscribed_price). Either way it's a one-shot: once notified, the
    subscription needs to be re-armed (re-subscribing) to fire again — see
    PriceDropService.subscribe.
    """
    if new_effective_price >= old_effective_price:
        return  # not a drop

    subscriptions = db.scalars(
        select(PriceDropSubscription).where(
            PriceDropSubscription.product_id == product_id,
            PriceDropSubscription.notified_at.is_(None),
        )
    ).all()
    if not subscriptions:
        return

    product = db.get(Product, product_id)
    if not product:
        return

    now = utcnow()
    for sub in subscriptions:
        threshold = sub.target_price if sub.target_price is not None else sub.subscribed_price
        if new_effective_price > threshold:
            continue

        db.add(
            OutboxEvent(
                topic="product.price_drop",
                payload={
                    "subscription_id": sub.id,
                    "email": sub.user.email,
                    "product_name": product.name,
                    "product_slug": product.slug,
                    "old_price": float(old_effective_price),
                    "new_price": float(new_effective_price),
                },
            )
        )
        sub.notified_at = now


class PriceDropService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = PriceDropCrud(db)

    def subscribe(
        self, user_id: int, product_id: int, target_price: Optional[float] = None
    ) -> PriceDropSubscriptionResponse:
        product = self.db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        current_price = product.effective_price
        if target_price is not None and target_price >= current_price:
            raise HTTPException(
                status_code=400,
                detail="Target price must be lower than the current price.",
            )

        # One row per (user, product) ever: re-subscribing after already
        # being notified (or just to change the target) re-arms the same
        # row rather than inserting a duplicate, which is what the unique
        # constraint actually expects.
        existing = self.crud.get_subscription(user_id, product_id)
        if existing:
            sub = self.crud.rearm_subscription(existing, current_price, target_price)
        else:
            sub = self.crud.create_subscription(user_id, product_id, current_price, target_price)

        return PriceDropSubscriptionResponse.model_validate(sub)

    def list_my_subscriptions(self, user_id: int) -> List[PriceDropSubscriptionResponse]:
        return [
            PriceDropSubscriptionResponse.model_validate(s)
            for s in self.crud.list_for_user(user_id)
        ]

    def unsubscribe(self, user_id: int, subscription_id: int) -> None:
        sub = self.crud.get_by_id(subscription_id)
        if not sub or sub.user_id != user_id:
            raise HTTPException(status_code=404, detail="Subscription not found")
        self.crud.delete(sub)
