from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.price_drop_subscription import PriceDropSubscription


class PriceDropCrud:
    def __init__(self, db: Session):
        self.db = db

    def get_subscription(self, user_id: int, product_id: int) -> Optional[PriceDropSubscription]:
        return self.db.scalars(
            select(PriceDropSubscription).where(
                PriceDropSubscription.user_id == user_id,
                PriceDropSubscription.product_id == product_id,
            )
        ).first()

    def create_subscription(
        self, user_id: int, product_id: int, subscribed_price: float, target_price: Optional[float]
    ) -> PriceDropSubscription:
        sub = PriceDropSubscription(
            user_id=user_id,
            product_id=product_id,
            subscribed_price=subscribed_price,
            target_price=target_price,
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def rearm_subscription(
        self, sub: PriceDropSubscription, subscribed_price: float, target_price: Optional[float]
    ) -> PriceDropSubscription:
        """Re-enable notification for a subscription that already fired,
        refreshing its baseline/target to the values given at re-subscribe
        time."""
        sub.notified_at = None
        sub.subscribed_price = subscribed_price
        sub.target_price = target_price
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def list_for_user(self, user_id: int) -> List[PriceDropSubscription]:
        stmt = (
            select(PriceDropSubscription)
            .where(PriceDropSubscription.user_id == user_id)
            .order_by(PriceDropSubscription.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, subscription_id: int) -> Optional[PriceDropSubscription]:
        return self.db.get(PriceDropSubscription, subscription_id)

    def delete(self, sub: PriceDropSubscription) -> None:
        self.db.delete(sub)
        self.db.commit()
