from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.coupon import Coupon
from app.schema.coupon_schema import CouponCreate, CouponUpdate
from typing import List, Optional

class CouponCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_coupon(self, coupon_data: CouponCreate) -> Coupon:
        coupon = Coupon(**coupon_data.model_dump())
        self.db.add(coupon)
        self.db.commit()
        self.db.refresh(coupon)
        return coupon

    def get_coupon_by_id(self, coupon_id: int) -> Optional[Coupon]:
        return self.db.execute(select(Coupon).where(Coupon.id == coupon_id)).scalar_one_or_none()

    def get_coupon_by_code(self, code: str) -> Optional[Coupon]:
        return self.db.execute(select(Coupon).where(Coupon.code == code)).scalar_one_or_none()

    def list_coupons(self, skip: int = 0, limit: int = 100) -> List[Coupon]:
        return list(self.db.execute(select(Coupon).offset(skip).limit(limit)).scalars().all())

    def update_coupon(self, coupon: Coupon, coupon_data: CouponUpdate) -> Coupon:
        update_data = coupon_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(coupon, key, value)
        self.db.commit()
        self.db.refresh(coupon)
        return coupon

    def delete_coupon(self, coupon: Coupon) -> None:
        self.db.delete(coupon)
        self.db.commit()

    def increment_usage(self, coupon: Coupon) -> None:
        coupon.used_count += 1
        self.db.commit()
