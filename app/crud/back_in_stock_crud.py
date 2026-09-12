from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.back_in_stock_subscription import BackInStockSubscription


class BackInStockCrud:
    def __init__(self, db: Session):
        self.db = db

    def get_subscription(
        self, user_id: int, product_id: int, variant_id: Optional[int]
    ) -> Optional[BackInStockSubscription]:
        return self.db.scalars(
            select(BackInStockSubscription).where(
                BackInStockSubscription.user_id == user_id,
                BackInStockSubscription.product_id == product_id,
                BackInStockSubscription.variant_id == variant_id,
            )
        ).first()

    def create_subscription(
        self, user_id: int, product_id: int, variant_id: Optional[int]
    ) -> BackInStockSubscription:
        sub = BackInStockSubscription(
            user_id=user_id, product_id=product_id, variant_id=variant_id
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def rearm_subscription(self, sub: BackInStockSubscription) -> BackInStockSubscription:
        """Re-enable notification for a subscription that already fired
        (or is already waiting — a no-op in that case)."""
        sub.notified_at = None
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def list_for_user(self, user_id: int) -> List[BackInStockSubscription]:
        stmt = (
            select(BackInStockSubscription)
            .where(BackInStockSubscription.user_id == user_id)
            .order_by(BackInStockSubscription.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, subscription_id: int) -> Optional[BackInStockSubscription]:
        return self.db.get(BackInStockSubscription, subscription_id)

    def delete(self, sub: BackInStockSubscription) -> None:
        self.db.delete(sub)
        self.db.commit()
