from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.loyalty_transaction import LoyaltyTransaction


class LoyaltyCrud:
    def __init__(self, db: Session):
        self.db = db

    def list_transactions(self, user_id: int, page: int = 1, page_size: int = 20) -> Tuple[int, List[LoyaltyTransaction]]:
        query = self.db.query(LoyaltyTransaction).filter(LoyaltyTransaction.user_id == user_id)
        total = query.count()

        offset = (page - 1) * page_size
        transactions = (
            query.order_by(LoyaltyTransaction.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return total, transactions
