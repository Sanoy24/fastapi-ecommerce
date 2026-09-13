from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.gift_card import GiftCard
from app.models.store_credit_transaction import StoreCreditTransaction
from app.models.user import User
from app.utils.gift_card import generate_gift_card_code
from app.utils.time import utcnow


class GiftCardCrud:
    def __init__(self, db: Session):
        self.db = db

    def issue(self, value: float, note: Optional[str], expires_at, created_by: int) -> GiftCard:
        gift_card = GiftCard(
            code=generate_gift_card_code(),
            value=value,
            note=note,
            expires_at=expires_at,
            created_by=created_by,
        )
        self.db.add(gift_card)
        self.db.commit()
        self.db.refresh(gift_card)
        return gift_card

    def get_by_code(self, code: str) -> Optional[GiftCard]:
        return self.db.query(GiftCard).filter(GiftCard.code == code.strip().upper()).first()

    def list_all(self, page: int = 1, page_size: int = 20) -> Tuple[int, List[GiftCard]]:
        query = self.db.query(GiftCard)
        total = query.count()
        offset = (page - 1) * page_size
        gift_cards = query.order_by(GiftCard.created_at.desc()).offset(offset).limit(page_size).all()
        return total, gift_cards

    def redeem(self, gift_card: GiftCard, user: User) -> GiftCard:
        if not gift_card.is_redeemable:
            detail = "Gift card has already been redeemed" if gift_card.is_redeemed else "Gift card has expired"
            raise HTTPException(status_code=400, detail=detail)

        gift_card.is_redeemed = True
        gift_card.redeemed_by_user_id = user.id
        gift_card.redeemed_at = utcnow()

        user.store_credit_balance = float(user.store_credit_balance) + float(gift_card.value)
        self.db.add(StoreCreditTransaction(
            user_id=user.id,
            gift_card_id=gift_card.id,
            amount=gift_card.value,
            transaction_type="redeem_gift_card",
            note=f"Redeemed gift card {gift_card.code}",
        ))

        self.db.commit()
        self.db.refresh(gift_card)
        return gift_card

    def list_store_credit_transactions(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[int, List[StoreCreditTransaction]]:
        query = self.db.query(StoreCreditTransaction).filter(StoreCreditTransaction.user_id == user_id)
        total = query.count()
        offset = (page - 1) * page_size
        transactions = (
            query.order_by(StoreCreditTransaction.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return total, transactions
