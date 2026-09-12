from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.back_in_stock_crud import BackInStockCrud
from app.models.back_in_stock_subscription import BackInStockSubscription
from app.models.outbox_event import OutboxEvent
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.schema.back_in_stock_schema import BackInStockSubscriptionResponse
from app.utils.time import utcnow


def notify_back_in_stock_subscribers(
    db: Session,
    *,
    product_id: int,
    variant_id: Optional[int],
    old_quantity: int,
    new_quantity: int,
) -> None:
    """Call this wherever stock_quantity is set on a Product or
    ProductVariant — see app/crud/product.py (bulk_update_inventory,
    update_product, update_product_variant) and
    app/api/v1/routes/admin.py (resolve_return's restock-on-approval) for
    the current call sites.

    Written as an explicit call at each site rather than a SQLAlchemy ORM
    event, matching how the rest of this codebase surfaces side effects
    (e.g. InventoryTransaction rows, outbox events) — nothing else here
    relies on implicit ORM hooks, so a new one would be the only place in
    the codebase working that way. The trade-off: a future new code path
    that increases stock has to remember to call this too.

    Writes an outbox event per matching subscription rather than sending
    email directly — this may run inside the same transaction as the
    stock update itself (see resolve_return), so if that transaction rolls
    back, the notification should never have been queued at all. See
    app/workers/arq_worker.py process_outbox_events_task for where
    "product.back_in_stock" events actually get turned into emails.
    """
    if old_quantity > 0 or new_quantity <= 0:
        return  # not a 0 -> positive transition

    subscriptions = db.scalars(
        select(BackInStockSubscription).where(
            BackInStockSubscription.product_id == product_id,
            BackInStockSubscription.variant_id == variant_id,
            BackInStockSubscription.notified_at.is_(None),
        )
    ).all()
    if not subscriptions:
        return

    product = db.get(Product, product_id)
    if not product:
        return

    now = utcnow()
    for sub in subscriptions:
        db.add(
            OutboxEvent(
                topic="product.back_in_stock",
                payload={
                    "subscription_id": sub.id,
                    "email": sub.user.email,
                    "product_name": product.name,
                    "product_slug": product.slug,
                },
            )
        )
        sub.notified_at = now


class BackInStockService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = BackInStockCrud(db)

    def subscribe(
        self, user_id: int, product_id: int, variant_id: Optional[int] = None
    ) -> BackInStockSubscriptionResponse:
        product = self.db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        if variant_id is not None:
            variant = self.db.get(ProductVariant, variant_id)
            if not variant or variant.product_id != product_id:
                raise HTTPException(status_code=404, detail="Variant not found for this product")
            available = variant.available_stock
        else:
            available = product.available_stock

        if available > 0:
            raise HTTPException(
                status_code=400,
                detail="This item is currently in stock — no need to subscribe.",
            )

        # One row per (user, product, variant) ever: re-subscribing after
        # already being notified re-arms the same row rather than
        # inserting a duplicate, which is what the unique constraint
        # actually expects.
        existing = self.crud.get_subscription(user_id, product_id, variant_id)
        if existing:
            sub = self.crud.rearm_subscription(existing)
        else:
            sub = self.crud.create_subscription(user_id, product_id, variant_id)

        return BackInStockSubscriptionResponse.model_validate(sub)

    def list_my_subscriptions(self, user_id: int) -> List[BackInStockSubscriptionResponse]:
        return [
            BackInStockSubscriptionResponse.model_validate(s)
            for s in self.crud.list_for_user(user_id)
        ]

    def unsubscribe(self, user_id: int, subscription_id: int) -> None:
        sub = self.crud.get_by_id(subscription_id)
        if not sub or sub.user_id != user_id:
            raise HTTPException(status_code=404, detail="Subscription not found")
        self.crud.delete(sub)
