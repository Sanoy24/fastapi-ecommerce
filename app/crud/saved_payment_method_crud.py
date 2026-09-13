from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.saved_payment_method import SavedPaymentMethod
from app.models.user import User


class SavedPaymentMethodCrud:
    def __init__(self, db: Session):
        self.db = db

    def get_user_stripe_customer_id(self, user_id: int) -> Optional[str]:
        user = self.db.get(User, user_id)
        return user.stripe_customer_id if user else None

    def set_user_stripe_customer_id(self, user_id: int, customer_id: str) -> None:
        self.db.execute(
            update(User).where(User.id == user_id).values(stripe_customer_id=customer_id)
        )
        self.db.commit()

    def get_by_stripe_payment_method_id(
        self, user_id: int, stripe_payment_method_id: str
    ) -> Optional[SavedPaymentMethod]:
        return self.db.scalars(
            select(SavedPaymentMethod).where(
                SavedPaymentMethod.user_id == user_id,
                SavedPaymentMethod.stripe_payment_method_id == stripe_payment_method_id,
            )
        ).first()

    def list_for_user(self, user_id: int) -> List[SavedPaymentMethod]:
        stmt = (
            select(SavedPaymentMethod)
            .where(SavedPaymentMethod.user_id == user_id)
            .order_by(SavedPaymentMethod.created_at)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, method_id: int) -> Optional[SavedPaymentMethod]:
        return self.db.get(SavedPaymentMethod, method_id)

    def unset_default_for_user(self, user_id: int) -> None:
        self.db.execute(
            update(SavedPaymentMethod)
            .where(SavedPaymentMethod.user_id == user_id, SavedPaymentMethod.is_default.is_(True))
            .values(is_default=False)
        )

    def create(
        self,
        user_id: int,
        stripe_payment_method_id: str,
        brand: str,
        last4: str,
        exp_month: int,
        exp_year: int,
        is_default: bool,
    ) -> SavedPaymentMethod:
        method = SavedPaymentMethod(
            user_id=user_id,
            stripe_payment_method_id=stripe_payment_method_id,
            brand=brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
        )
        self.db.add(method)
        self.db.commit()
        self.db.refresh(method)
        return method

    def set_default(self, method: SavedPaymentMethod) -> SavedPaymentMethod:
        self.unset_default_for_user(method.user_id)
        method.is_default = True
        self.db.commit()
        self.db.refresh(method)
        return method

    def delete(self, method: SavedPaymentMethod) -> None:
        self.db.delete(method)
        self.db.commit()

    def promote_oldest_to_default(self, user_id: int) -> None:
        """Called after deleting a user's default method: if any are left,
        make the oldest one the new default rather than leaving the user
        with none."""
        remaining = self.list_for_user(user_id)
        if remaining:
            remaining[0].is_default = True
            self.db.commit()
